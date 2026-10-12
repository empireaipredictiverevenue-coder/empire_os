import {test} from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {createRequire} from "node:module";
import {createChallenge, verifyProof, challengeText} from "../scripts/verify_bsc_treasury_control.mjs";

const require = createRequire(import.meta.url);
const {Wallet} = require("../contracts/escrow/node_modules/ethers");
const NOW = Date.parse("2026-10-12T09:25:00Z");

function privateDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "empire-wallet-proof-test-"));
}
function record(dir, wallet) {
  const file=path.join(dir,"challenge.json");
  return createChallenge(file,NOW,wallet.address);
}

test("offline EIP191 challenge is exact-domain-bound and no-transaction", async()=>{
  const wallet=Wallet.createRandom(),dir=privateDir();
  const c=record(dir,wallet);
  assert.equal(c.network_chain_id,56);
  assert.match(c.message,/Empire AI \/ EmpireOS/);
  assert.match(c.message,/empire-ai\.co\.uk/);
  assert.match(c.message,/No transactions, token approvals/);
  assert.match(c.message,/Wallet: 0x/);
  assert.equal(fs.statSync(path.join(dir,"challenge.json")).mode & 0o777,0o600);
  const sig=await wallet.signMessage(c.message);
  const verified=verifyProof(c,sig,NOW+60000,wallet.address);
  assert.equal(verified.address_control_proved,true);
  assert.equal(verified.candidate_wallet,wallet.address);
  assert.equal(verified.funds_moved,false);
  assert.equal(verified.payment_collection_activated,false);
  assert.equal(verified.human_corporate_beneficial_owner_independently_verified,false);
  assert.equal(verified.financial_operator_authorized,false);
});
test("incorrect wallet is held and no proof can be inferred",async()=>{
  const wallet=Wallet.createRandom(),wrong=Wallet.createRandom(),dir=privateDir();
  const c=record(dir,wallet);
  const sig=await wrong.signMessage(c.message);
  assert.throws(()=>verifyProof(c,sig,NOW,wallet.address),/does not control candidate wallet/);
  assert.throws(()=>verifyProof(c,sig,NOW),/unexpected challenge binding/);
});
test("challenge expiry, message tampering and nonce changes are held",async()=>{
  const wallet=Wallet.createRandom(),dir=privateDir();
  const c=record(dir,wallet);
  const sig=await wallet.signMessage(c.message);
  assert.throws(()=>verifyProof(c,sig,NOW+49*60*60*1000,wallet.address),/expired or invalid/);
  assert.throws(()=>verifyProof({...c,message:c.message+" MONEY APPROVED"},sig,NOW,wallet.address),/tampering/);
  assert.throws(()=>verifyProof({...c,nonce:"0x"+"0".repeat(48)},sig,NOW,wallet.address),/tampering/);
  assert.throws(()=>verifyProof({...c,network_chain_id:1},sig,NOW,wallet.address),/unexpected challenge/);
});
test("signature format and malformed control attempts fail closed",async()=>{
  const wallet=Wallet.createRandom(),dir=privateDir();
  const c=record(dir,wallet);
  for (const s of ["", "0x1234", "sig", "0x"+"a".repeat(130)]) {
    assert.throws(()=>verifyProof(c,s,NOW,wallet.address),/invalid EIP-191 signature|invalid signature format/);
  }
});
test("reusing the same challenge destination never overwrites original nonce",()=>{
  const wallet=Wallet.createRandom(),dir=privateDir();
  const file=path.join(dir,"challenge.json");
  createChallenge(file,NOW,wallet.address);
  const original=fs.readFileSync(file,"utf8");
  assert.throws(()=>createChallenge(file,NOW,wallet.address),/EEXIST/);
  assert.equal(fs.readFileSync(file,"utf8"),original);
});
test("challenge for production is pinned to existing recorded wallet",()=>{
  const dir=privateDir();
  const challenge=createChallenge(path.join(dir,"challenge.json"),NOW);
  assert.equal(challenge.candidate_wallet,"0x1339b487046B0ad924a10c20b1791608EA8595a8");
  assert.equal(challenge.actual_funds_moved,false);
  assert.equal(challenge.production_payment_activation,false);
  assert.equal(challenge.message,challengeText(challenge.candidate_wallet,challenge.nonce,challenge.issued_at,challenge.expires_at));
});
