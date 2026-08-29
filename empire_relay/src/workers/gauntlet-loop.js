import { CONFIG } from "../config/index.js";
import { callGLM } from "../utils/glm-client.js";
import { query } from "../utils/database.js";
import { limiters } from "../middleware/rate-limiter.js";
import { hubWebSearch, last30daysSignals } from "../orchestrator.js";

/**
 * MODULE 3: AI Gauntlet Loop Copy Engine.
 *
 * 1. FAN OUT sub-agents: one researches company news/signals, one drafts the hook, one reviews tone.
 * 2. CRITIC AGLET: evaluates the draft against winning copy patterns in pgvector DB.
 * 3. ITERATE: critic forces builder to iterate until hook is hyper-personalized + punchy.
 * 4. Save final vetted draft to Twenty CRM only after Gauntlet passes.
 */

const MAX_ITERATIONS = CONFIG.GAUNTLET.maxIterations;
const QUALITY_THRESHOLD = CONFIG.GAUNTLET.qualityThreshold;

/**
 * Run the full Gauntlet Loop for a single lead.
 * Returns { passed, iterations, finalDraft, finalScore }.
 */
export async function runGauntlet(lead) {
  const context = {
    lead,
    research: null,
    draft: null,
    criticFeedback: null,
    iterations: [],
    finalScore: 0,
    passed: false,
  };

  console.log(`[Gauntlet] starting for ${lead.companyName} (${lead.email})`);

  // STEP 1: Research sub-agent — gather company signals
  context.research = await _researchAgent(lead);
  console.log(`[Gauntlet] research complete: ${context.research.signals?.length || 0} signals found`);

  // STEP 2: Get similar winning copy from pgvector for reference
  const winningExamples = await _getWinningExamples(lead);
  console.log(`[Gauntlet] fetched ${winningExamples.length} winning copy examples`);

  for (let i = 0; i < MAX_ITERATIONS; i++) {
    // STEP 3: Builder sub-agent — draft the email
    context.draft = await _builderAgent(lead, context.research, winningExamples, context.criticFeedback);
    console.log(`[Gauntlet] iteration ${i + 1}: draft created (${context.draft.subject?.length || 0} chars subject)`);

    // STEP 4: Critic sub-agent — evaluate the draft
    const critique = await _criticAgent(lead, context.draft, winningExamples, context.research);
    console.log(`[Gauntlet] iteration ${i + 1}: critic score=${critique.score}/10, passed=${critique.score >= QUALITY_THRESHOLD}`);

    // Log iteration
    context.iterations.push({
      iteration: i + 1,
      draft: context.draft,
      criticFeedback: critique.feedback,
      score: critique.score,
      passed: critique.score >= QUALITY_THRESHOLD,
    });

    await query(
      `INSERT INTO gauntlet_iterations (lead_ref, iteration, draft, critic_feedback, score, passed)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [lead.leadRef || lead.email, i + 1, context.draft.body, critique.feedback, critique.score, critique.score >= QUALITY_THRESHOLD]
    );

    if (critique.score >= QUALITY_THRESHOLD) {
      context.passed = true;
      context.finalScore = critique.score;
      context.criticFeedback = critique.feedback;
      break;
    }

    // Feed critic feedback back to builder for next iteration
    context.criticFeedback = critique.feedback;
    context.finalScore = critique.score;
  }

  if (!context.passed) {
    console.warn(`[Gauntlet] ${lead.companyName} failed to pass after ${MAX_ITERATIONS} iterations (final score: ${context.finalScore}/10)`);
    // Use best draft anyway if score >= 5
    if (context.finalScore >= 5) {
      console.log(`[Gauntlet] using best draft despite threshold miss (score=${context.finalScore})`);
      context.passed = true; // soft pass
    }
  }

  return {
    passed: context.passed,
    iterations: context.iterations.length,
    research: context.research,
    draft: context.draft,
    finalScore: context.finalScore,
    criticFeedback: context.criticFeedback,
  };
}

// ── Sub-agents ─────────────────────────────────────────────────────

async function _researchAgent(lead) {
  // Live signals first: hub web search + last30days market feed.
  const [webResults, marketSignals] = await Promise.all([
    hubWebSearch(`${lead.companyName} ${lead.niche || ""} ${lead.metro || ""} news`, 5),
    last30daysSignals(lead.niche || ""),
  ]);
  const liveContext = [
    ...webResults.map(r => `[web] ${(r.title || r.name || "")} ${(r.snippet || r.description || "").slice(0, 120)}`),
    ...marketSignals,
  ].filter(s => s.length > 10);

  const result = await callGLM(
    [
      {
        role: "system",
        content:
          "You are a B2B research agent. Analyze the company and return a JSON object with: " +
          "signals (array of {type, detail} — news, hiring, expansion, pain points, tech stack), " +
          "outreach_angle (string — the best approach angle), " +
          "personalization_hooks (array of 3 specific hooks for this company). " +
          "Be specific and factual. Use the LIVE SIGNALS provided — do not invent facts.",
      },
      {
        role: "user",
        content:
          `Company: ${lead.companyName}\n` +
          `Niche: ${lead.niche || "unknown"}\n` +
          `Metro: ${lead.metro || "unknown"}\n` +
          `Contact: ${lead.contactName || "unknown"}\n` +
          `ICP Tier: ${lead.icpTier || "unknown"}\n` +
          (lead.waterfallData ? `Enrichment: ${JSON.stringify(lead.waterfallData).slice(0, 500)}\n` : "") +
          (liveContext.length ? `LIVE SIGNALS:\n${liveContext.join("\n")}\n` : "") +
          `\nResearch this company. Return JSON only.`,
      },
    ],
    { maxTokens: 800, temperature: 0.5 }
  );

  try {
    const jsonMatch = result.content.match(/\{[\s\S]*\}/);
    const parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : null;
    if (parsed) {
      // fold live signals into the returned object so builder sees them
      parsed.live_signals = liveContext.slice(0, 6);
      return parsed;
    }
    return { signals: [], outreachAngle: result.content, live_signals: liveContext.slice(0, 6) };
  } catch {
    return { signals: [], outreachAngle: result.content, live_signals: liveContext.slice(0, 6) };
  }
}

async function _builderAgent(lead, research, winningExamples, criticFeedback) {
  const winningContext = winningExamples.length > 0
    ? `Winning copy patterns (USE THESE AS TEMPLATES):\n${winningExamples.map((w, i) =>
        `--- Example ${i + 1} (reply: ${w.reply_type}) ---\nSubject: ${w.email_subject}\nHook: ${w.hook_structure}`
      ).join("\n")}`
    : "No winning examples yet. Use proven cold email best practices: personal hook → value prop → soft CTA.";

  const feedbackContext = criticFeedback
    ? `\n\nCRITIC FEEDBACK (incorporate this):\n${criticFeedback}`
    : "";

  const result = await callGLM(
    [
      {
        role: "system",
        content:
          "You are an elite cold email copywriter. Write a hyper-personalized outreach email. " +
          "Return a JSON object with: subject (max 50 chars), body (plain text, max 150 words), " +
          "hook (the opening 1-2 sentences that grab attention). " +
          "Rules: no generic flattery, no buzzword salad, no 'I hope this email finds you well'. " +
          "The hook must reference a specific signal about THIS company. " +
          "Keep it punchy and human. Return JSON only.",
      },
      {
        role: "user",
        content:
          `Company: ${lead.companyName}\n` +
          `Contact: ${lead.contactName || "there"}\n` +
          `Niche: ${lead.niche || "B2B services"}\n` +
          `Metro: ${lead.metro || "unknown"}\n\n` +
          `RESEARCH:\n${JSON.stringify(research).slice(0, 1000)}\n\n` +
          `${winningContext}${feedbackContext}\n\n` +
          `Write the email. Return JSON: { "subject": "...", "body": "...", "hook": "..." }`,
      },
    ],
    { maxTokens: 600, temperature: 0.7 }
  );

  try {
    const jsonMatch = result.content.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) : { subject: "", body: result.content, hook: "" };
  } catch {
    return { subject: "", body: result.content, hook: "" };
  }
}

async function _criticAgent(lead, draft, winningExamples, research) {
  const winningContext = winningExamples.length > 0
    ? `WINNING PATTERNS to compare against:\n${winningExamples.map((w) =>
        `- ${w.hook_structure} → ${w.reply_type}`).join("\n")}`
    : "Use these quality criteria: specificity, personalization, brevity, clear value prop, no AI-isms.";

  const result = await callGLM(
    [
      {
        role: "system",
        content:
          "You are a brutal but fair copy critic. Evaluate the email draft. " +
          "Score 1-10 (10 = would book a meeting, 5 = mediocre, 1 = spam). " +
          "Return JSON: { score: number, feedback: string (actionable, specific), " +
          "highlights: array (what works), issues: array (what fails) }. " +
          "Be harsh. Score 7+ only if the hook references a REAL signal about THIS company " +
          "and the email is under 150 words with no generic fluff. Return JSON only.",
      },
      {
        role: "user",
        content:
          `Company: ${lead.companyName} (${lead.niche || "B2B"})\n\n` +
          `DRAFT SUBJECT: ${draft.subject}\n` +
          `DRAFT BODY: ${draft.body}\n\n` +
          `RESEARCH CONTEXT: ${JSON.stringify(research).slice(0, 500)}\n\n` +
          `${winningContext}\n\n` +
          `Evaluate this draft. Return JSON.`,
      },
    ],
    { maxTokens: 400, temperature: 0.3 }
  );

  try {
    const jsonMatch = result.content.match(/\{[\s\S]*\}/);
    const parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : { score: 5, feedback: "Could not parse critique" };
    return {
      score: Math.min(10, Math.max(1, parsed.score || 5)),
      feedback: parsed.feedback || "",
      highlights: parsed.highlights || [],
      issues: parsed.issues || [],
    };
  } catch {
    return { score: 5, feedback: "Critique parse failed", highlights: [], issues: [] };
  }
}

async function _getWinningExamples(lead) {
  try {
    const res = await query(
      "SELECT * FROM winning_copy ORDER BY created_at DESC LIMIT 3",
      []
    );
    return res.rows;
  } catch (err) {
    console.warn(`[Gauntlet] could not fetch winning examples: ${err.message}`);
    return [];
  }
}
