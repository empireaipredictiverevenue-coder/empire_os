/** Pure consumer contract for the existing EmpireOS Search Intelligence reader.

It shows only operational reader readiness for Empire AI's *own* site.
No market claims, prospect rows, GSC metrics or ROI calculation overrides.
*/
export type RoiPublicReaderStatus = Readonly<{
  ready: boolean;
  status: "OWNER_READER_CONNECTED" | "NOT_ACTIVATED" | "SOURCE_NOT_VERIFIED";
  checkedAt: string | null;
}>;
const fail=(status:RoiPublicReaderStatus["status"]="SOURCE_NOT_VERIFIED"):RoiPublicReaderStatus=>({
  ready:false,status,checkedAt:null,
});
const isRecord=(v:unknown):v is Record<string,unknown> =>
  v!==null && typeof v==="object" && !Array.isArray(v);

/** Any unrecognized, stale, non-OBSERVE or privileged source fails closed. */
export function reviewPublicReaderStatus(
  payload: unknown,
  now: Date = new Date(),
): RoiPublicReaderStatus {
  if(!isRecord(payload) ||
     payload.schema_version!=="empire.roi.public_search_reader_status.v1" ||
     payload.source!=="SEARCH_INTELLIGENCE" ||
     payload.owner_site!=="empire-ai.co.uk" ||
     payload.mode!=="OBSERVE" ||
     payload.execution_authority!=="none" ||
     payload.public_evidence_released!==false ||
     payload.sector_evidence_ready!==false ||
     payload.commercial_outcome_verified!==false) return fail();

  if(payload.connection_status==="NOT_ACTIVATED" &&
     payload.reader_ready===false && payload.reader_checked_at===null) return fail("NOT_ACTIVATED");
  if(payload.connection_status!=="OWNER_READER_CONNECTED" ||
     payload.reader_ready!==true ||
     typeof payload.reader_checked_at!=="string" ||
     !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(payload.reader_checked_at)) return fail();
  const checked=Date.parse(payload.reader_checked_at),clock=now.getTime();
  if(!Number.isFinite(checked) || !Number.isFinite(clock) ||
     clock-checked>300_000 || checked-clock>30_000) return fail();

  return {ready:true,status:"OWNER_READER_CONNECTED",
    checkedAt:payload.reader_checked_at};
}
