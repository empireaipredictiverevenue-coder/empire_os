import pg from "pg";
import { CONFIG } from "../config/index.js";

const pool = new pg.Pool({
  host: CONFIG.PG.host,
  port: CONFIG.PG.port,
  database: CONFIG.PG.database,
  user: CONFIG.PG.user,
  password: CONFIG.PG.password,
  max: 10,
  idleTimeoutMillis: 30_000,
});

pool.on("error", (err) => console.error("[PG] idle client error", err.message));

export async function query(text, params) {
  const client = await pool.connect();
  try {
    const res = await client.query(text, params);
    return res;
  } finally {
    client.release();
  }
}

// ── Winning copy (pgvector) ──────────────────────────────────────

export async function saveWinningCopy(entry) {
  const { leadRef, companyName, emailSubject, emailBody, hookStructure, replyType, embedding } = entry;
  // Store embedding as JSON array string — pgvector accepts '[0.1, 0.2, ...]'
  const embStr = embedding ? JSON.stringify(embedding) : null;
  await query(
    `INSERT INTO winning_copy (lead_ref, company_name, email_subject, email_body, hook_structure, reply_type, embedding)
     VALUES ($1, $2, $3, $4, $5, $6, $7::vector)`,
    [leadRef, companyName, emailSubject, emailBody, hookStructure, replyType, embStr]
  );
  console.log(`[PG] saved winning copy for ${companyName} (${replyType})`);
}

export async function getSimilarWinningCopies(queryEmbedding, limit = 5) {
  const embStr = JSON.stringify(queryEmbedding);
  const res = await query(
    `SELECT * FROM winning_copy
     ORDER BY embedding <-> $1::vector
     LIMIT $2`,
    [embStr, limit]
  );
  return res.rows;
}

export async function getRecentWinningCopies(limit = 10) {
  const res = await query(
    `SELECT * FROM winning_copy ORDER BY created_at DESC LIMIT $1`,
    [limit]
  );
  return res.rows;
}

// ── Lead dedup ───────────────────────────────────────────────────

export async function dedupLead(leadRef) {
  const res = await query(
    `SELECT id FROM lead_dedup WHERE lead_ref = $1`,
    [leadRef]
  );
  return res.rows.length > 0;
}

export async function saveLead(lead) {
  const { leadRef, companyName, email, source, waterfallData } = lead;
  if (await dedupLead(leadRef)) {
    return { deduped: true };
  }
  await query(
    `INSERT INTO lead_dedup (lead_ref, company_name, email, source, waterfall_data)
     VALUES ($1, $2, $3, $4, $5)`,
    [leadRef, companyName, email, source, JSON.stringify(waterfallData || {})]
  );
  return { deduped: false };
}

export async function getLeadCount() {
  const res = await query("SELECT COUNT(*) as count FROM lead_dedup", []);
  return parseInt(res.rows[0].count, 10);
}

// ── Initialize tables (idempotent) ────────────────────────────────

export async function ensureSchema() {
  await query(`
    CREATE TABLE IF NOT EXISTS winning_copy (
      id SERIAL PRIMARY KEY,
      lead_ref TEXT,
      company_name TEXT,
      email_subject TEXT,
      email_body TEXT,
      hook_structure TEXT,
      reply_type TEXT,
      created_at TIMESTAMP DEFAULT NOW(),
      embedding VECTOR(1024)
    )
  `);
  await query(`
    CREATE TABLE IF NOT EXISTS lead_dedup (
      id SERIAL PRIMARY KEY,
      lead_ref TEXT UNIQUE,
      company_name TEXT,
      email TEXT,
      source TEXT,
      waterfall_data JSONB,
      created_at TIMESTAMP DEFAULT NOW()
    )
  `);
  await query(`
    CREATE TABLE IF NOT EXISTS gauntlet_iterations (
      id SERIAL PRIMARY KEY,
      lead_ref TEXT,
      iteration INT,
      draft TEXT,
      critic_feedback TEXT,
      score INT,
      passed BOOLEAN,
      created_at TIMESTAMP DEFAULT NOW()
    )
  `);
  await query(`
    CREATE TABLE IF NOT EXISTS self_heal_log (
      id SERIAL PRIMARY KEY,
      module TEXT,
      error TEXT,
      stack_trace TEXT,
      fix_applied TEXT,
      success BOOLEAN,
      created_at TIMESTAMP DEFAULT NOW()
    )
  `);
  console.log("[PG] schema ensured");
}

export { pool };
