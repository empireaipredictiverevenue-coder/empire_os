import {test} from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {commercialOfferCategory} from "../apps/empire-public-site/src/lib/commercial-offer-category.ts";

test("commercial proposal categories reflect actual offer families",()=>{
  assert.equal(commercialOfferCategory("consultancy"),"Consultancy and advisory");
  assert.equal(commercialOfferCategory("digital_avatar"),"Digital Avatar — scoped deployment");
  assert.equal(commercialOfferCategory("intelligence_product"),
    "Intelligence product — scoped one-time delivery");
  assert.equal(commercialOfferCategory("unknown"),"Commercial proposal — scope requires review");
});

test("commercial page uses the correct category instead of a binary default",()=>{
  const source=fs.readFileSync(new URL("../apps/empire-public-site/src/app/commercial/page.tsx",import.meta.url),"utf8");
  assert.match(source,/commercialOfferCategory\(offer\.offer_family\)/);
  assert.doesNotMatch(source,/offer\.offer_family === "consultancy" \? "Consultancy and advisory"/);
  assert.match(source,/consultancy, intelligence products and Digital Avatar solutions/);
});
