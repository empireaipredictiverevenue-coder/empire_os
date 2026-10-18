import test from "node:test";
import assert from "node:assert/strict";
import {
  organicTouchFromSearch,
  linkedCommercialHref,
  commercialTouchFromSearch,
} from "../apps/empire-public-site/src/lib/organic-campaign-touch.ts";

const cid = "campaign_" + "a".repeat(24);
const query = new URLSearchParams({
  utm_campaign: cid,
  utm_content: cid + ":linkedin",
  utm_source: "linkedin",
  utm_medium: "organic_social",
}).toString();

test("one-hop industry to commercial token preserves strict known parameters", () => {
  const href = linkedCommercialHref("?" + query, "/industries/solar");
  assert.ok(href.startsWith("/commercial?"));
  const got = commercialTouchFromSearch(new URL(href, "https://empire-ai.co.uk").search);
  assert.deepEqual(got, {
    campaign_id: cid, asset_id: cid + ":linkedin",
    source: "linkedin", medium: "organic_social",
    landing_path: "/industries/solar",
  });
});

test("newsletter and youtube source pairs roundtrip with no browser storage", () => {
  for (const [source, medium, channel] of [
    ["owned_newsletter", "email", "newsletter"],
    ["youtube", "organic_video", "youtube"],
  ]) {
    const params = new URLSearchParams({
      utm_campaign: cid, utm_content: cid + ":" + channel,
      utm_source: source, utm_medium: medium,
    });
    const href = linkedCommercialHref(params.toString(), "/industries/roofing");
    assert.equal(
      commercialTouchFromSearch(new URL(href, "https://empire-ai.co.uk").search)?.source,
      source,
    );
  }
});

test("reject external, unrelated, duplicate, malformed and mismatched tokens", () => {
  assert.equal(linkedCommercialHref(query, "/personal/account"), "/commercial");
  assert.equal(linkedCommercialHref("", "/industries/solar"), "/commercial");
  assert.equal(linkedCommercialHref(query.replace("linkedin", "google"), "/industries/solar"), "/commercial");
  assert.equal(
    organicTouchFromSearch(query + "&utm_campaign=" + cid, "/industries/solar"),
    null,
  );
  assert.equal(commercialTouchFromSearch(query), null);
  assert.equal(commercialTouchFromSearch(query + "&utm_landing=/account/private"), null);
  assert.equal(commercialTouchFromSearch(query + "&utm_landing=https://evil.test"), null);
});
