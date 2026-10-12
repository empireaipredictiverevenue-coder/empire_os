#!/usr/bin/env node
/**
 * Empire AI first-party BSC treasury control proof.
 *
 * challenge: emits a one-time, time-limited EIP-191 personal_sign message.
 * verify: reads a signature from a private 0600 file (never CLI args),
 *         recovers the EVM signer and creates an auditable no-funds receipt.
 *
 * Signing proves control of the specified *public* address at that moment.
 * It does NOT approve transactions, custody, settlement, BSC contract
 * deployment, signer permissions, or grant financial operational authority.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const {getAddress, verifyMessage} = require(path.join(here, "../contracts/escrow/node_modules/ethers"));

const CANDIDATE = "0x1339b487046B0ad924a10c20b1791608EA8595a8";
const CHAIN = 56;
const DURATION_MS = 48 * 60 * 60 * 1000;
const MAX_BYTES = 10000;

function fail(message) {
  throw new Error("BSC_WALLET_PROOF_HELD: " + message);
}
function safeRead(file) {
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077) !== 0 || stat.size > MAX_BYTES) {
    fail("proof file must be a private, ordinary file with mode 0600");
  }
  return fs.readFileSync(file, "utf8");
}
function createOnce(file, data) {
  if (!path.isAbsolute(file)) fail("absolute path required");
  const fd = fs.openSync(file, "wx", 0o600);
  try {
    fs.writeFileSync(fd, data, "utf8");
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
}
export function challengeText(candidate, nonce, issued, expiry) {
  return [
    "Empire AI / EmpireOS — BSC Treasury Control Verification",
    "Domain: empire-ai.co.uk",
    "Network: BNB Smart Chain Mainnet (chain ID 56)",
    "Wallet: " + getAddress(candidate),
    "Nonce: " + nonce,
    "Issued: " + issued,
    "Expires: " + expiry,
    "",
    "Purpose: Prove control of the existing public receiving address only.",
    "No transactions, token approvals, funds transfers, escrow deployment,",
    "role grants, binding orders, payment collection or commercial terms",
    "are authorised by signing this message.",
  ].join("\n");
}
export function createChallenge(file, now = Date.now(), expectedWallet = CANDIDATE) {
  const nonce = "0x" + crypto.randomBytes(24).toString("hex");
  const issued = new Date(now).toISOString();
  const expiry = new Date(now + DURATION_MS).toISOString();
  const record = {
    schema_version: "empire.bsc-treasury-control-challenge.v1",
    candidate_wallet: getAddress(expectedWallet),
    network_chain_id: CHAIN,
    nonce,
    issued_at: issued,
    expires_at: expiry,
    message: challengeText(expectedWallet, nonce, issued, expiry),
    actual_funds_moved: false,
    production_payment_activation: false,
  };
  createOnce(file, JSON.stringify(record, null, 2) + "\n");
  return record;
}
export function verifyProof(challenge, signature, now = Date.now(), expectedWallet = CANDIDATE) {
  if (!challenge || challenge.schema_version !== "empire.bsc-treasury-control-challenge.v1" ||
      challenge.candidate_wallet !== getAddress(expectedWallet) ||
      challenge.network_chain_id !== CHAIN) fail("unexpected challenge binding");
  if (typeof challenge.nonce !== "string" || !/^0x[0-9a-f]{48}$/.test(challenge.nonce)) {
    fail("invalid nonce");
  }
  const issuedAt = Date.parse(challenge.issued_at);
  const expiresAt = Date.parse(challenge.expires_at);
  if (!Number.isFinite(issuedAt) || !Number.isFinite(expiresAt) ||
      expiresAt !== issuedAt + DURATION_MS ||
      issuedAt > now + 60000 || now > expiresAt) fail("challenge expired or invalid");
  if (challenge.message !== challengeText(
    expectedWallet, challenge.nonce, challenge.issued_at, challenge.expires_at
  )) fail("message tampering detected");
  if (typeof signature !== "string" || !/^0x[0-9a-fA-F]{130}$/.test(signature.trim())) {
    fail("invalid signature format");
  }
  let recovered;
  try { recovered = getAddress(verifyMessage(challenge.message, signature.trim())); }
  catch { fail("invalid EIP-191 signature"); }
  if (recovered !== getAddress(expectedWallet)) fail("signature does not control candidate wallet");
  return {
    schema_version: "empire.bsc-treasury-control-proof.v1",
    candidate_wallet: recovered,
    challenge_nonce: challenge.nonce,
    challenge_issued_at: challenge.issued_at,
    verified_at: new Date(now).toISOString(),
    method: "EIP-191 personal_sign",
    address_control_proved: true,
    contract_wallet_EIP1271_proved: false,
    human_corporate_beneficial_owner_independently_verified: false,
    escrow_beneficiary_independently_approved: false,
    BSC_mainnet_contract_deployed: false,
    financial_operator_authorized: false,
    funds_moved: false,
    payment_collection_activated: false,
  };
}
function usage() {
  console.error("Usage: node scripts/verify_bsc_treasury_control.mjs challenge ABSOLUTE_CHALLENGE_PATH");
  console.error("       node scripts/verify_bsc_treasury_control.mjs verify ABSOLUTE_CHALLENGE_PATH PRIVATE_SIGNATURE_FILE PRIVATE_RECEIPT_PATH");
  process.exit(2);
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const [cmd, a, b, c] = process.argv.slice(2);
    if (cmd === "challenge" && a && !b) {
      const record = createChallenge(a);
      console.log(JSON.stringify({status:"CHALLENGE_CREATED",path:a,wallet:record.candidate_wallet,expires_at:record.expires_at,message:record.message}));
    } else if (cmd === "verify" && a && b && c) {
      const challenge = JSON.parse(safeRead(a));
      const signature = safeRead(b).trim();
      const result = verifyProof(challenge, signature);
      createOnce(c, JSON.stringify(result, null, 2) + "\n");
      console.log(JSON.stringify({status:"WALLET_ADDRESS_CONTROL_VERIFIED",receipt:c,detail:result}));
    } else usage();
  } catch (error) {
    console.error(error instanceof Error && String(error.message).startsWith("BSC_WALLET_PROOF_HELD:")
      ? error.message : "BSC_WALLET_PROOF_HELD: verification unavailable");
    process.exit(2);
  }
}