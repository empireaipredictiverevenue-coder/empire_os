import express from "express";
import cors from "cors";
import { CONFIG } from "../config/index.js";
import { limiters } from "../middleware/rate-limiter.js";
import { withSelfHeal } from "../utils/self-healing.js";

/**
 * MODULE 1: Relay Server — webhook receiver from Twenty CRM.
 *
 * Listens for POST /webhooks/twenty
 * When a person's stage changes to 'QUALIFIED':
 *   - Parse email + first name
 *   - Fire Resend cold outreach email via port 443 (HTTPS)
 *   - Return 200 OK immediately, process email in background
 */
export function createRelayServer(app) {
  const router = express.Router();

  // Twenty CRM webhook — stage change to QUALIFIED
  router.post("/webhooks/twenty", async (req, res) => {
    const payload = req.body;

    // Acknowledge immediately to prevent timeout
    res.status(200).json({ received: true, processing: "async" });

    // Process in background
    _processQualifiedLead(payload).catch((err) => {
      console.error("[Relay] background processing failed:", err.message);
    });
  });

  // Resend inbound reply webhook
  router.post("/webhooks/resend-inbound", async (req, res) => {
    res.status(200).json({ received: true });

    _processInboundReply(req.body).catch((err) => {
      console.error("[Relay] inbound reply processing failed:", err.message);
    });
  });

  // Health check
  router.get("/health", (req, res) => {
    res.json({ status: "ok", module: "relay", timestamp: new Date().toISOString() });
  });

  return router;
}

async function _processQualifiedLead(payload) {
  // Handle both empty-stage and stage-update shapes from Twenty
  const person = payload?.data?.person || payload?.person || payload?.data || {};
  const stage = payload?.data?.stage || payload?.stage || "";
  const email = person?.email || payload?.email || "";
  const firstName = person?.firstName || person?.first_name || person?.name?.split(" ")[0] || "";
  const companyName = person?.companyName || person?.company_name || "";

  if (!email) {
    console.warn("[Relay] no email in payload, skipping");
    return;
  }

  // Check if stage is QUALIFIED (case insensitive)
  if (stage.toUpperCase() !== "QUALIFIED") {
    console.log(`[Relay] stage=${stage}, not QUALIFIED, skipping ${email}`);
    return;
  }

  console.log(`[Relay] QUALIFIED lead: ${firstName} <${email}> at ${companyName}`);

  // Fire Resend email
  const sendFn = withSelfHeal(_sendResendEmail, { module: "Resend.sendQualified" });
  await sendFn({ email, firstName, companyName });
}

async function _sendResendEmail({ email, firstName, companyName }) {
  await limiters.resend.waitForSlot();

  const subject = firstName
    ? `${firstName}, qualified leads for ${companyName || "your business"}`
    : "Qualified leads for your business";

  const html = _buildOutreachEmail(firstName, companyName);

  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${CONFIG.RESEND.apiKey}`,
    },
    body: JSON.stringify({
      from: CONFIG.RESEND.from,
      to: [email],
      subject,
      html,
      reply_to: CONFIG.RESEND.from,
    }),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Resend API ${resp.status}: ${text.slice(0, 200)}`);
  }

  const data = await resp.json();
  console.log(`[Relay] email sent to ${email} — id: ${data.id}`);
  return data;
}

async function _processInboundReply(payload) {
  // Resend inbound webhook format
  const from = payload?.data?.from || payload?.from || "";
  const subject = payload?.data?.subject || payload?.subject || "";
  const body = payload?.data?.text || payload?.text || "";
  const messageId = payload?.data?.messageId || payload?.messageId || "";

  console.log(`[Relay] inbound reply from ${from}: ${subject}`);

  // Store reply for learning engine (Module 4 picks this up)
  // Signal via Redis pub/sub that a reply was received
  const { redis } = await import("../middleware/rate-limiter.js");
  await redis.publish("inbound:reply", JSON.stringify({
    from,
    subject,
    body,
    messageId,
    timestamp: new Date().toISOString(),
  }));

  console.log("[Relay] inbound reply published to learning engine");
}

function _buildOutreachEmail(firstName, companyName) {
  const name = firstName || "there";
  const company = companyName || "your company";

  return `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #0e1422;">Hi ${name},</h2>
  <p>We noticed ${company} operates in a sector where we have a steady flow of qualified leads.
  Our lead-generation marketplace connects service businesses with ready-to-buy customers —
  no upfront cost, only pay per qualified lead.</p>
  <p style="margin: 24px 0;">
    <a href="https://empire-ai.co.uk" style="background: #39ff88; color: #03060a; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
      See Available Leads
    </a>
  </p>
  <p>Would you be open to a quick chat to see if this is a fit?</p>
  <p style="color: #6b7894; font-size: 14px; margin-top: 32px;">
    Empire AI — Lead generation marketplace<br>
    <a href="https://empire-ai.co.uk">empire-ai.co.uk</a>
  </p>
</body>
</html>`;
}
