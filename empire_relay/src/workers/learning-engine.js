import { CONFIG } from "../config/index.js";
import { callGLM } from "../utils/glm-client.js";
import { saveWinningCopy, getRecentWinningCopies, query } from "../utils/database.js";
import { redis } from "../middleware/rate-limiter.js";

/**
 * MODULE 4: Closed-Loop Learning Engine.
 *
 * 1. Monitor reply webhooks from Resend + Twenty CRM (via Redis pub/sub).
 * 2. When a positive reply or booked meeting comes in, capture the successful
 *    email copy, hook structure, and company profile.
 * 3. Write winning examples back into pgvector database.
 * 4. Daily review function: GLM-5.2 queries winning examples to refine future outreach.
 */

/**
 * Start the learning engine — subscribes to Redis pub/sub for reply events.
 */
export async function startLearningEngine() {
  const subscriber = redis.duplicate();

  await subscriber.subscribe("inbound:reply");
  await subscriber.subscribe("twenty:positive-reply");
  await subscriber.subscribe("twenty:meeting-booked");

  subscriber.on("message", async (channel, message) => {
    console.log(`[Learning] received event on ${channel}`);
    try {
      const data = JSON.parse(message);
      await _captureWinningCopy(data, channel);
    } catch (err) {
      console.error(`[Learning] failed to capture from ${channel}: ${err.message}`);
    }
  });

  console.log("[Learning] engine started, listening for reply events");
  return subscriber;
}

/**
 * Capture a winning copy example and save to pgvector.
 */
async function _captureWinningCopy(event, channel) {
  const {
    from: fromEmail,
    subject: replySubject,
    body: replyBody,
    messageId,
    leadRef,
    companyName,
    originalEmailSubject,
    originalEmailBody,
    originalHook,
    replyType: rawReplyType,
  } = event;

  // Classify reply type
  const replyType = rawReplyType || _classifyReply(replySubject, replyBody, channel);
  console.log(`[Learning] capturing ${replyType} from ${fromEmail}`);

  // Only save positive replies + meetings (not "unsubscribe" or "not interested")
  if (!["positive", "meeting-booked", "interested"].includes(replyType)) {
    console.log(`[Learning] skipping ${replyType} reply from ${fromEmail}`);
    return;
  }

  // Generate embedding for the email copy (for pgvector similarity search)
  const embedding = await _generateEmbedding(originalEmailBody || replyBody || "");

  await saveWinningCopy({
    leadRef: leadRef || messageId || fromEmail,
    companyName: companyName || fromEmail,
    emailSubject: originalEmailSubject || replySubject,
    emailBody: originalEmailBody || replyBody,
    hookStructure: originalHook || originalEmailSubject,
    replyType,
    embedding,
  });

  console.log(`[Learning] saved winning copy: ${companyName} (${replyType})`);
}

/**
 * Classify whether a reply is positive, negative, or neutral.
 */
function _classifyReply(subject, body, channel) {
  if (channel === "twenty:meeting-booked") return "meeting-booked";
  if (channel === "twenty:positive-reply") return "positive";

  const text = (subject + " " + body).toLowerCase();

  const positiveSignals = [
    "interested", "yes", "sure", "let's talk", "schedule", "meeting",
    "call", "demo", "more info", "tell me more", "sounds good",
    "when are you free", "available", "booked", "how much",
  ];

  const negativeSignals = [
    "unsubscribe", "not interested", "remove", "stop", "no thanks",
    "spam", "do not contact", "opt out", "never", "don't",
  ];

  if (negativeSignals.some((s) => text.includes(s))) return "negative";
  if (positiveSignals.some((s) => text.includes(s))) return "positive";
  return "neutral";
}

/**
 * Generate a text embedding using GLM-5.2.
 * Falls back to a hash-based pseudo-embedding if API fails.
 */
async function _generateEmbedding(text) {
  try {
    // Use GLM chat to generate a summary which we hash into a pseudo-embedding.
    // Real embeddings would use a dedicated model; this is pragmatic for pgvector.
    const result = await callGLM(
      [
        { role: "system", content: "Output 16 key metrics about this email as a JSON array of numbers 0-1. Metrics: personalization, brevity, specificity, hook_strength, cta_clarity, value_prop, tone_match, urgency, credibility, uniqueness, industry_fit, pain_point_relevance, social_proof, curiosity, simplicity, conversion_likelihood." },
        { role: "user", content: text.slice(0, 500) },
      ],
      { maxTokens: 200, temperature: 0.2 }
    );

    const match = result.content.match(/\[[\s\S]*\]/);
    if (match) {
      const scores = JSON.parse(match[0]);
      // Expand 16 scores to 1024 dimensions by tiling (pragmatic embedding for pgvector)
      const embedding = [];
      for (let i = 0; i < 1024; i++) {
        embedding.push(scores[i % scores.length] || 0.5);
      }
      return embedding;
    }
  } catch (err) {
    console.warn(`[Learning] embedding generation failed: ${err.message}`);
  }

  // Fallback: hash-based pseudo-embedding
  return _hashEmbedding(text, 1024);
}

function _hashEmbedding(text, dims) {
  const embedding = new Array(dims).fill(0);
  for (let i = 0; i < text.length; i++) {
    const charCode = text.charCodeAt(i);
    // Bernstein hash variant
    embedding[i % dims] = (embedding[i % dims] * 33 + charCode) % 1000 / 1000;
  }
  return embedding;
}

/**
 * Daily refinement — GLM-5.2 analyzes winning copies to extract patterns.
 * Runs once per day (scheduled by Module 7 orchestrator).
 */
export async function runDailyRefinement() {
  console.log("[Learning] starting daily refinement...");
  const winners = await getRecentWinningCopies(20);

  if (winners.length === 0) {
    console.log("[Learning] no winning copies yet, skipping refinement");
    return { status: "no_data" };
  }

  const analysis = await callGLM(
    [
      {
        role: "system",
        content:
          "You are an outreach copy analyst. Analyze the winning email patterns and return a JSON object with: " +
          "top_hooks (array of strings — the best hook structures), " +
          "common_subjects (array — winning subject line patterns), " +
          "best_angles (array — outreach angles that got replies), " +
          "anti_patterns (array — things to avoid based on what did NOT work). " +
          "Be specific. Return JSON only.",
      },
      {
        role: "user",
        content:
          `WINNING COPIES (${winners.length} examples):\n` +
          winners.map((w, i) =>
            `--- ${i + 1} (${w.reply_type}) ---\n` +
            `Subject: ${w.email_subject}\n` +
            `Hook: ${w.hook_structure}\n` +
            `Company: ${w.company_name}`
          ).join("\n\n"),
      },
    ],
    { maxTokens: 600, temperature: 0.4 }
  );

  let parsed = {};
  try {
    const jsonMatch = analysis.content.match(/\{[\s\S]*\}/);
    parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : { raw: analysis.content };
  } catch {
    parsed = { raw: analysis.content };
  }

  // Store refinement result
  await query(
    `INSERT INTO self_heal_log (module, error, stack_trace, fix_applied, success)
     VALUES ($1, $2, $3, $4, $5)`,
    ["learning-daily", "n/a", "n/a", `Refined patterns: ${JSON.stringify(parsed).slice(0, 500)}`, true]
  );

  console.log("[Learning] daily refinement complete:", JSON.stringify(parsed).slice(0, 200));
  return parsed;
}
