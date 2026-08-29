import { CONFIG } from "../config/index.js";
import { limiters } from "../middleware/rate-limiter.js";
import { saveLead, dedupLead, getLeadCount } from "../utils/database.js";
import { withSelfHeal } from "../utils/self-healing.js";
import { callGLM } from "../utils/glm-client.js";
import Database from "better-sqlite3";
import { promises as fs } from "fs";

/**
 * MODULE 2: Lead & Waterfall Ingestor.
 *
 * 1. Connect to our custom waterfall system to fetch raw company data + verified emails.
 * 2. Run deduplication check against pgvector database — never process same lead twice.
 * 3. Automatically push clean, enriched lead profiles into Twenty CRM via REST API.
 * 4. Automated error log + retry loop — failed API calls never drop a lead.
 *
 * Sources: existing SQLite hub DB (833K leads), Serper search, enrichment cascade.
 */

const SQLITE_DB = CONFIG.HUB_DB_PATH;

/**
 * Pull leads from existing Empire OS SQLite DB (lane_leads table).
 * The 1.8GB DB lives inside the empire-hub container, so we query via incus exec.
 * Streams in batches to avoid memory pressure.
 */
export async function* streamSQLiteLeads(batchSize = 50, offset = 0) {
  const { execSync } = await import("child_process");

  let currentOffset = offset;
  while (true) {
    // Get already-processed prospect IDs to exclude via SQL
    const processedCount = await _getProcessedCount();
    // Use a simple LIMIT query — no offset needed since we skip deduped in the app layer
    const sql = `SELECT prospect_id, business_name, email, metro, niche, phone, score, classified_tier, payout_per_lead, endpoint_url, active FROM si_buyer_outreach WHERE email IS NOT NULL AND email != '' ORDER BY prospect_id DESC LIMIT ${batchSize * 3}`;
    // Write SQL to temp file, execute via incus, read JSON result
    const { promises: fs } = await import("fs");
    const tmpSql = `/tmp/lead_query_${Date.now()}.sql`;
    const tmpPy = `/tmp/lead_query_${Date.now()}.py`;
    await fs.writeFile(tmpSql, sql, "utf-8");
    const pyScript = `import sqlite3,json
c=sqlite3.connect('/root/empire_os/empire_os.db')
c.row_factory=sqlite3.Row
sql=open('/tmp/_lead_q.sql').read()
rows=c.execute(sql).fetchall()
print(json.dumps([dict(r) for r in rows]))
c.close()`;
    await fs.writeFile(tmpPy, pyScript, "utf-8");

    let result = "";
    try {
      // Push SQL file into container
      execSync(`incus file push ${tmpSql} empire-hub/tmp/_lead_q.sql 2>/dev/null`, { timeout: 10_000 });
      execSync(`incus file push ${tmpPy} empire-hub/tmp/_lead_q.py 2>/dev/null`, { timeout: 10_000 });
      result = execSync(`incus exec empire-hub -- python3 /tmp/_lead_q.py`, {
        timeout: 30_000,
        encoding: "utf-8",
        maxBuffer: 10 * 1024 * 1024,
      }).trim();
    } finally {
      await fs.unlink(tmpSql).catch(() => {});
      await fs.unlink(tmpPy).catch(() => {});
    }

    let rows = [];
    try { rows = JSON.parse(result); } catch { break; }

    if (rows.length === 0) break;
    yield rows;

    // If all rows in this batch were already processed, we're done
    let newCount = 0;
    for (const row of rows) {
      if (!await dedupLead(row.prospect_id)) newCount++;
    }
    if (newCount === 0) {
      console.log("[Ingestor] all leads in batch already deduped, stopping");
      break;
    }
    currentOffset += batchSize;
  }
}

async function _getProcessedCount() {
  return getLeadCount();
}

/**
 * Waterfall enrichment — fetch company data from multiple sources.
 * Uses Serper API for search + our existing enrichment cascade.
 */
export async function fetchWaterfallData(companyName, niche, metro) {
  await limiters.waterfall.waitForSlot();

  const waterfallData = {
    company: companyName,
    niche,
    metro,
    sources: {},
    timestamp: new Date().toISOString(),
  };

  // Source 1: Serper search for company details
  if (CONFIG.SERPER_KEY) {
    try {
      const serperResult = await _serperSearch(`${companyName} ${niche} ${metro}`);
      waterfallData.sources.serper = serperResult;
    } catch (err) {
      console.warn(`[Ingestor] Serper failed for ${companyName}: ${err.message}`);
      waterfallData.sources.serper = { error: err.message };
    }
  }

  // Source 2: GLM-5.2 company classification
  try {
    const classification = await _glmClassifyCompany(companyName, niche, metro);
    waterfallData.classification = classification;
  } catch (err) {
    console.warn(`[Ingestor] GLM classification failed: ${err.message}`);
  }

  return waterfallData;
}

async function _serperSearch(query) {
  await limiters.waterfall.waitForSlot();

  const resp = await fetch("https://google.serper.dev/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-KEY": CONFIG.SERPER_KEY,
    },
    body: JSON.stringify({ q: query, num: 5 }),
  });

  if (!resp.ok) throw new Error(`Serper ${resp.status}`);
  const data = await resp.json();

  return {
    organic: (data.organic || []).slice(0, 3).map((r) => ({
      title: r.title,
      link: r.link,
      snippet: r.snippet,
    })),
    knowledgeGraph: data.knowledgeGraph ? {
      title: data.knowledgeGraph.title,
      description: data.knowledgeGraph.description,
    } : null,
  };
}

async function _glmClassifyCompany(companyName, niche, metro) {
  const result = await callGLM(
    [
      {
        role: "system",
        content: "You are a B2B lead classifier. Analyze the company and return a JSON object with: industry, company_size_est, decision_maker_title, outreach_angle, pain_points (array of 3), value_prop_hint. Be concise.",
      },
      {
        role: "user",
        content: `Company: ${companyName}\nNiche: ${niche}\nMetro: ${metro}\n\nClassify this company. Return JSON only.`,
      },
    ],
    { maxTokens: 500, temperature: 0.3 }
  );

  try {
    // Extract JSON from response
    const jsonMatch = result.content.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) : { raw: result.content };
  } catch {
    return { raw: result.content };
  }
}

/**
 * Push a lead to Twenty CRM via REST API.
 * Uses self-healing wrapper for automatic recovery.
 */
export async function pushToTwentyCrm(lead) {
  const pushFn = withSelfHeal(_twentyCreatePerson, {
    module: "TwentyCRM.createPerson",
    filePath: null,
  });

  return pushFn(lead);
}

async function _twentyCreatePerson(lead) {
  await limiters.twenty.waitForSlot();

  if (!CONFIG.TWENTY.apiKey) {
    console.warn("[Ingestor] Twenty CRM API key not set, skipping push");
    return { skipped: true, reason: "no_api_key" };
  }

  const personBody = {
    data: {
      firstName: lead.contactName?.split(" ")[0] || "",
      lastName: lead.contactName?.split(" ").slice(1).join(" ") || "",
      email: { email: lead.email, isPrimary: true },
      companyName: lead.businessName || "",
      city: lead.metro || "",
      // Custom fields for niche/ICP
      position: lead.niche || "",
      // Stage: new lead
      stage: "NEW",
    },
  };

  const resp = await fetch(`${CONFIG.TWENTY.url}/rest/people`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${CONFIG.TWENTY.apiKey}`,
    },
    body: JSON.stringify(personBody),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Twenty CRM ${resp.status}: ${text.slice(0, 200)}`);
  }

  const data = await resp.json();
  console.log(`[Ingestor] pushed ${lead.businessName} to Twenty CRM — id: ${data.data?.id}`);
  return data;
}

/**
 * Main ingestor loop — process leads in batches.
 * 1. Pull from SQLite
 * 2. Dedup via pgvector
 * 3. Enrich via waterfall
 * 4. Push to Twenty CRM
 */
export async function runIngestorLoop(opts = {}) {
  const { batchSize = 50, maxLeads = 200, dryRun = false } = opts;
  let processed = 0;
  let skipped = 0;
  let failed = 0;

  console.log(`[Ingestor] starting batch (batchSize=${batchSize}, maxLeads=${maxLeads}, dryRun=${dryRun})`);

  for await (const batch of streamSQLiteLeads(batchSize)) {
    for (const lead of batch) {
      if (processed >= maxLeads) break;

      const leadRef = lead.prospect_id || `${lead.business_name}_${lead.email}`;
      const companyName = lead.business_name || "Unknown";
      const niche = lead.niche || "unknown";
      const metro = lead.metro || "unknown";
      const email = lead.email || "";
      const icpTier = lead.classified_tier || "unknown";

      // Dedup
      if (await dedupLead(leadRef)) {
        skipped++;
        continue;
      }

      // Enrich (skip in dry run)
      let waterfallData = null;
      if (!dryRun) {
        waterfallData = await fetchWaterfallData(
          companyName,
          niche,
          metro
        ).catch((err) => {
          console.warn(`[Ingestor] waterfall failed: ${err.message}`);
          return null;
        });
      }

      // Save to dedup table
      await saveLead({
        leadRef,
        companyName,
        email,
        source: "si_buyer_outreach",
        waterfallData,
      });

      // Push to Twenty CRM (skip in dry run or if no API key)
      if (!dryRun && CONFIG.TWENTY.apiKey && email) {
        try {
          await pushToTwentyCrm({
            contactName: "",
            businessName: companyName,
            email,
            metro,
            niche,
          });
          processed++;
        } catch (err) {
          console.error(`[Ingestor] push failed for ${companyName}: ${err.message}`);
          failed++;
        }
      } else {
        console.log(`[Ingestor] ${dryRun ? "dry-run " : ""}stored: ${companyName} (${email})`);
        processed++;
      }
    }

    if (processed >= maxLeads) {
      console.log(`[Ingestor] reached maxLeads=${maxLeads}`);
      break;
    }
  }

  const total = await getLeadCount();
  console.log(
    `[Ingestor] done: processed=${processed}, skipped(dedup)=${skipped}, failed=${failed}, total_in_db=${total}`
  );

  return { processed, skipped, failed, totalInDb: total };
}
