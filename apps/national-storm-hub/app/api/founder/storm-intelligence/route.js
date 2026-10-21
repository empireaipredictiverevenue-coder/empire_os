import {NextResponse} from "next/server";
import {readFile} from "node:fs/promises";
import {FOUNDER_HEADERS,verifyFounderRequest} from "../../../../lib/founder-auth.js";
import {projectEmpireStormRuntime} from "../../../../lib/storm-intelligence-bridge.js";

export const runtime="nodejs";
export const dynamic="force-dynamic";
const SNAPSHOT="/srv/empire_os/runtime/storm_opportunity/latest.json";
const reply=(obj,status=200)=>NextResponse.json(obj,{status,headers:FOUNDER_HEADERS});
export async function GET(req){
  const state=verifyFounderRequest(req.headers);
  if(state==="NOT_CONFIGURED")return reply({status:"FOUNDER_ACCESS_NOT_CONFIGURED"},503);
  if(state!=="AUTHORIZED")return reply({error:"Founder authentication required"},401);
  try{
    const raw=JSON.parse(await readFile(SNAPSHOT,"utf8"));
    return reply(projectEmpireStormRuntime(raw));
  }catch{
    return reply({status:"UNAVAILABLE",reason:"CANONICAL_STORM_RUNTIME_SNAPSHOT_UNAVAILABLE",execution_authority:"none"},503);
  }
}
