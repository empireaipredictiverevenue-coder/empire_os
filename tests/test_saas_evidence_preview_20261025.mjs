// Source-contract tests: no browser visit, customer data or server writes.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const page = fs.readFileSync(
  new URL("../apps/empire-public-site/src/app/predictive-revenue/page.tsx", import.meta.url),
  "utf8",
);
const preview = fs.readFileSync(
  new URL("../apps/empire-public-site/src/components/SaaSRevenueEvidencePreview.tsx", import.meta.url),
  "utf8",
);

test("original first party deployment contract and consent remain untouched", () => {
  assert.match(page, /id="deployment-request"/);
  assert.match(page, /\/v1\/checkout\/predictive-revenue\/interests/);
  assert.match(page, /contact_consent: contactConsent/);
  assert.match(page, /idempotency_key: attempt\.idempotencyKey/);
  assert.match(page, /type="checkbox" required checked=\{contactConsent\}/);
  assert.match(page, /result\?\.decision === "deployment_interest_recorded"/);
  assert.match(page, /<SaaSRevenueEvidencePreview \/>/);
  assert.match(page, /<PredictiveRevenueBuyerExplanation \/>/);
  assert.match(page, /<SaaSRevenueLeakageGuide \/>/);
});

test("public example is meaningful, interactive and accessible without a submission", () => {
  for (const item of ["Lead to demo", "Trial to contract", "Deal to cash"]) {
    assert.ok(preview.includes(item));
  }
  assert.match(preview, /useState/);
  assert.match(preview, /aria-pressed=/);
  assert.match(preview, /aria-labelledby="evidence-sample-title"/);
  assert.match(preview, /id="free-evidence-sample"/);
  assert.match(preview, /href="#deployment-request"/);
  assert.match(preview, /Example only — no customer data/);
  assert.match(preview, /A customer-specific diagnostic needs permitted real records/);
  assert.match(preview, /Seller-estimated deal value is not a customer commitment/);
});

test("example has no rogue PII, synthetic metrics, provider calls or hidden send path", () => {
  assert.doesNotMatch(preview, /\bfetch\s*\(|\baxios\b|XMLHttpRequest|WebSocket/);
  assert.doesNotMatch(preview, /localStorage|sessionStorage|navigator\.sendBeacon/);
  assert.doesNotMatch(preview, /type=["'](email|tel|password)["']/);
  assert.doesNotMatch(preview, /<form\b|\bonSubmit\s*=|mailto:/);
  assert.doesNotMatch(preview, /\b(20|30|40|50|100)% (?:conversion|increase|uplift|accuracy)/i);
  assert.match(preview, /No new\s+mailing list, payment or data collection/);
  assert.match(preview, /"use client"/);
});
