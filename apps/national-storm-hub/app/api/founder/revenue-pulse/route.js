import {NextResponse} from "next/server";
import {readFile} from "node:fs/promises";
import {createHash,timingSafeEqual} from "node:crypto";
import {prepareFounderPulse} from "../../../../lib/revenue-pulse-website.js";
export const runtime="nodejs";
export const dynamic="force-dynamic";
const SNAPSHOT="/srv/empire_os/runtime/revenue_pulse/latest.json";
const HEADERS={"Cache-Control":"private, no-store, max-age=0","Vary":"Authorization","X-Robots-Tag":"noindex, nofollow"};
const respond=(obj,status=200)=>NextResponse.json(obj,{status,headers:HEADERS});
export async function GET(req){
  // Key set by server-owned systemd EnvironmentFile, never NEXT_PUBLIC_ or bundled.
  const secret=process.env.NSH_FOUNDER_PULSE_KEY;
  if(!secret||secret.length<48)return respond({status:"FOUNDER_ACCESS_NOT_CONFIGURED"},503);
  const bearer=req.headers.get("authorization")||"";
  if(!bearer.startsWith("Bearer ")||bearer.length>260)return respond({error:"Founder authentication required"},401);
  const candidate=bearer.slice(7);
  const expected=createHash("sha256").update(secret).digest();
  const actual=createHash("sha256").update(candidate).digest();
  if(!timingSafeEqual(expected,actual))return respond({error:"Founder authentication required"},401);
  try {
    const source=JSON.parse(await readFile(SNAPSHOT,"utf8"));
    return respond(prepareFounderPulse(source));
  }catch {
    return respond({status:"CANONICAL_REVENUE_PULSE_UNAVAILABLE",scope:"GLOBAL_EMPIRE_AI",national_storm_hub:{status:"TENANT_ACCOUNTING_NOT_CONNECTED"}},503);
  }
}
