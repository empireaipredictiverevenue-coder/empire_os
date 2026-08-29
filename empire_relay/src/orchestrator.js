import express from "express";
import cors from "cors";
import { CONFIG } from "../config/index.js";
import { createRelayServer } from "./routes/relay-server.js";
import { ensureSchema, query } from "./utils/database.js";
import { redis } from "./middleware/rate-limiter.js";
import { startLearningEngine, runDailyRefinement } from "./workers/learning-engine.js";
import { runIngestorLoop } from "./workers/lead-ingestor.js";
import { runGauntlet } from "./workers/gauntlet-loop.js";
import { callGLM } from "./utils/glm-client.js";
import { promises as fs } from "fs";

/**
 * MODULE 7: MASTER DOMINANT MULTI-STRATEGY AGENT (FULL ORCHESTRATION).
 *
 * Wires all modules together:
 *   1. Relay server (Express port 3000)
 *   2. Lead waterfall ingestor (background worker)
 *   3. GLM-5.2 Gauntlet Loop (on-demand + worker)
 *   4. Closed-loop learning engine (Redis pub/sub listener)
 *   5. Rate limiter (Redis — initialized)
 *   6. Self-healing diagnostics (wrapped around all API calls)
 *   7. Organic content syndicator (daily worker)
 *
 * All in one process for the Vultr VPS.
 */

const app = express();

app.use(cors());
app.use(express.json({ limit: "2mb" }));
app.use(express.urlencoded({ extended: true }));

// ── Routes ─────────────────────────────────────────────────────────

const relayRouter = createRelayServer(app);
app.use("/", relayRouter);

// Gauntlet trigger endpoint
app.post("/api/gauntlet/run", async (req, res) => {
  const lead = req.body?.lead;
  if (!lead?.companyName) {
    return res.status(400).json({ error: "lead.companyName required" });
  }

  res.status(202).json({ status: "processing", lead: lead.companyName });

  try {
    const result = await runGauntlet(lead);
    console.log(`[Orchestrator] gauntlet result: passed=${result.passed}, score=${result.finalScore}`);
    // TODO: push winning draft to Twenty CRM
  } catch (err) {
    console.error("[Orchestrator] gauntlet failed:", err.message);
  }
});

// Ingestor trigger endpoint
app.post("/api/ingestor/run", async (req, res) => {
  const { batchSize, maxLeads, dryRun } = req.body || {};
  res.status(202).json({ status: "processing" });

  try {
    const result = await runIngestorLoop({
      batchSize: batchSize || 50,
      maxLeads: maxLeads || 200,
      dryRun: dryRun !== false,
    });
    console.log("[Orchestrator] ingestor result:", result);
  } catch (err) {
    console.error("[Orchestrator] ingestor failed:", err.message);
  }
});

// Hub web-search helper: single-flight fetch of hub /v1/web/search results.
// Hub runs INSIDE the empire-hub container (port 8000 proxy on host via incusd),
// not on host localhost:8081 — route through the container.
export async function hubWebSearch(q, num = 5) {
  const urls = [
    `http://127.0.0.1:8000/v1/web/search?q=${encodeURIComponent(q)}&num=${num}`,
    `http://127.0.0.1:8081/v1/web/search?q=${encodeURIComponent(q)}&num=${num}`,
  ];
  for (const u of urls) {
    try {
      const r = await fetch(u, { signal: AbortSignal.timeout(15000) });
      if (!r.ok) continue;
      const d = await r.json();
      const res = d.results || d.organic || [];
      if (res.length) return res;
    } catch { continue; }
  }
  return [];
}

// Last30days signal bridge: pull recent market signals from the last30days
// agent artifacts (hub feedback dir) and return compact strings usable
// as research context in the Gauntlet builder prompt. Works from host
// (reads /root/feedback directly) or container (via /dev/vda2 mount path
// resolved from HUB_DB_PATH).
export async function last30daysSignals(queryHint = "") {
  const candidates = [
    "/root/feedback/last30days_runs.jsonl",
    process.env.HUB_DB_PATH ? process.env.HUB_DB_PATH.replace(/\/[^/]+$/, "/../feedback/last30days_runs.jsonl") : null,
  ].filter(Boolean);
  for (const p of candidates) {
    try {
      const fs = await import("fs");
      const fd = fs.openSync(p, "r");
      const size = fs.fstatSync(fd).size;
      const buf = Buffer.alloc(Math.min(size, 120000));
      fs.readSync(fd, buf, 0, buf.length, Math.max(0, size - buf.length));
      fs.closeSync(fd);
      const lines = buf.toString("utf-8").split("\n").filter(l => l.trim());
      let d = {};
      for (let i = lines.length - 1; i >= 0; i--) {
        try { d = JSON.parse(lines[i]); break; } catch { continue; }
      }
      const results = d?.data?.results || [];
      return results
        .filter(r => !queryHint ||
          `${r.summary || ""} ${r.title || ""} ${d.topic || ""}`.toLowerCase().includes(queryHint.toLowerCase()))
        .slice(0, 6)
        .map(r => `[${d.topic || "market"}] ${(r.summary || r.title || "").slice(0, 140)} (${r.source || "?"}, ${r.published_at || "?"})`);
    } catch { continue; }
  }
  return [];
}

// Daily refinement trigger
app.post("/api/learning/refine", async (req, res) => {
  res.status(202).json({ status: "processing" });
  try {
    const result = await runDailyRefinement();
    console.log("[Orchestrator] refinement:", result);
  } catch (err) {
    console.error("[Orchestrator] refinement failed:", err.message);
  }
});

// Content syndicator trigger
app.post("/api/content/remix", async (req, res) => {
  res.status(202).json({ status: "processing" });
  try {
    const result = await runContentSyndicator();
    console.log("[Orchestrator] content syndicator:", result);
  } catch (err) {
    console.error("[Orchestrator] content syndicator failed:", err.message);
  }
});

// Dashboard status endpoint
app.get("/api/status", async (req, res) => {
  const [leadCount, winningCount, healCount] = await Promise.all([
    query("SELECT COUNT(*) as c FROM lead_dedup", []).then((r) => r.rows[0]?.c || 0).catch(() => 0),
    query("SELECT COUNT(*) as c FROM winning_copy", []).then((r) => r.rows[0]?.c || 0).catch(() => 0),
    query("SELECT COUNT(*) as c, SUM(CASE WHEN success THEN 1 ELSE 0 END) as ok FROM self_heal_log", [])
      .then((r) => ({ total: r.rows[0]?.c || 0, ok: r.rows[0]?.ok || 0 })).catch(() => ({ total: 0, ok: 0 })),
  ]);

  res.json({
    status: "operational",
    modules: {
      relay: "active",
      ingestor: "ready",
      gauntlet: "ready",
      learning: "listening",
      rateLimiter: "active",
      selfHealing: "active",
      contentSyndicator: "ready",
    },
    metrics: {
      leadsInDb: parseInt(leadCount, 10),
      winningCopies: parseInt(winningCount, 10),
      selfHealEvents: healCount,
    },
    config: {
      glmModel: CONFIG.GLM.model,
      port: CONFIG.PORT,
      redis: "connected",
    },
    timestamp: new Date().toISOString(),
  });
});

// ── ORGANIC CONTENT SYNDICATOR ─────────────────────────────────────

/**
 * Parse internal transcripts and remix insights into multi-channel social posts daily.
 * Pulls from Empire OS feedback directory + generates social posts via GLM-5.2.
 */
export async function runContentSyndicator() {
  // Find recent analysis files
  const feedbackDir = "/root/empire_os/feedback";
  const files = await _getRecentFiles(feedbackDir, 5);

  if (files.length === 0) {
    console.log("[Content] no recent transcripts found");
    return { status: "no_content" };
  }

  const posts = [];
  for (const file of files) {
    const content = await fs.readFile(file, "utf-8").catch(() => "");
    if (content.length < 100) continue;

    const socialPosts = await _remixToSocialPosts(content, file);
    posts.push({ source: file, posts: socialPosts });
  }

  // Save syndicated posts
  const outputDir = "/root/empire_os/empire_relay/logs";
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(
    `${outputDir}/syndicated_posts_${Date.now()}.json`,
    JSON.stringify(posts, null, 2),
    "utf-8"
  );

  return { filesProcessed: files.length, postsGenerated: posts.length };
}

async function _getRecentFiles(dir, max) {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    const files = entries
      .filter((e) => e.isFile() && (e.name.endsWith(".json") || e.name.endsWith(".txt")))
      .map((e) => `${dir}/${e.name}`);

    // Sort by modification time (most recent first)
    const stats = await Promise.all(
      files.map(async (f) => ({
        file: f,
        mtime: (await fs.stat(f)).mtimeMs,
      }))
    );
    return stats.sort((a, b) => b.mtime - a.mtime).slice(0, max).map((s) => s.file);
  } catch {
    return [];
  }
}

async function _remixToSocialPosts(transcript, sourceFile) {
  const result = await callGLM(
    [
      {
        role: "system",
        content:
          "You are a content marketer. Take this transcript/analysis and remix it into 3 social posts: " +
          "1) LinkedIn (professional, with insight + takeaway, max 400 chars), " +
          "2) X/Twitter (punchy hook + thread teasers, max 280 chars), " +
          "3) YouTube Short concept (title + 15s script concept). " +
          "Return JSON array: [{ platform, content }]. Make it value-driven, not salesy.",
      },
      { role: "user", content: `Source: ${sourceFile}\n\nContent:\n${transcript.slice(0, 2000)}` },
    ],
    { maxTokens: 800, temperature: 0.6 }
  );

  try {
    const jsonMatch = result.content.match(/\[[\s\S]*\]/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) : [{ platform: "raw", content: result.content }];
  } catch {
    return [{ platform: "raw", content: result.content }];
  }
}

// ── STARTUP ───────────────────────────────────────────────────────

async function bootstrap() {
  console.log("╔══════════════════════════════════════════════════╗");
  console.log("║   EMPIRE AI — MASTER RELAY SERVER v1.0         ║");
  console.log("║   GLM-5.2 | Redis | pgvector | Resend | Twenty ║");
  console.log("╚══════════════════════════════════════════════════╝");

  // Ensure DB schema
  await ensureSchema();

  // Start learning engine (Redis pub/sub)
  await startLearningEngine();

  // Start Express
  app.listen(CONFIG.PORT, () => {
    console.log(`[Orchestrator] listening on :${CONFIG.PORT}`);
    console.log(`[Orchestrator] GLM-5.2: ${CONFIG.GLM.model} @ ${CONFIG.GLM.baseUrl}`);
    console.log(`[Orchestrator] Redis: ${CONFIG.REDIS_URL}`);
    console.log(`[Orchestrator] Postgres: ${CONFIG.PG.host}:${CONFIG.PG.port}/${CONFIG.PG.database}`);
    console.log(`[Orchestrator] Resend: ${CONFIG.RESEND.from}`);
    console.log("");
    console.log("Modules:");
    console.log("  1. Relay (webhooks):    GET  /health");
    console.log("  2. Ingestor:            POST /api/ingestor/run");
    console.log("  3. Gauntlet Loop:       POST /api/gauntlet/run");
    console.log("  4. Learning:            POST /api/learning/refine");
    console.log("  5. Rate limiter:        active (Redis)");
    console.log("  6. Self-healing:        active (GLM-5.2)");
    console.log("  7. Content syndicator:  POST /api/content/remix");
    console.log("");
    console.log("Status: GET /api/status");
  });

  // Handle graceful shutdown
  process.on("SIGTERM", () => {
    console.log("[Orchestrator] SIGTERM, shutting down...");
    process.exit(0);
  });
  process.on("SIGINT", () => {
    console.log("[Orchestrator] SIGINT, shutting down...");
    process.exit(0);
  });
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  bootstrap().catch((err) => {
    console.error("FATAL:", err);
    process.exit(1);
  });
}

export { app };
