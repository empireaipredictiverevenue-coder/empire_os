import {NextResponse} from "next/server";
import {readFile} from "node:fs/promises";
import {FOUNDER_HEADERS,verifyFounderRequest} from "../../../../lib/founder-auth.js";
import {prepareFounderPulse} from "../../../../lib/revenue-pulse-website.js";
export const runtime="nodejs";
export const dynamic="force-dynamic";
const SNAPSHOT="/srv/empire_os/runtime/revenue_pulse/latest.json";
const HEADERS=FOUNDER_HEADERS;
const respond=(obj,status=200)=>NextResponse.json(obj,{status,headers:HEADERS});
export async function GET(req){
  const access=verifyFounderRequest(req.headers);
  if(access==="NOT_CONFIGURED")return respond({status:"FOUNDER_ACCESS_NOT_CONFIGURED"},503);
  if(access!=="AUTHORIZED")return respond({error:"Founder authentication required"},401);
  try {
    const source=JSON.parse(await readFile(SNAPSHOT,"utf8"));
    return respond(prepareFounderPulse(source));
  }catch {
    return respond({status:"CANONICAL_REVENUE_PULSE_UNAVAILABLE",scope:"GLOBAL_EMPIRE_AI",national_storm_hub:{status:"TENANT_ACCOUNTING_NOT_CONNECTED"}},503);
  }
}
