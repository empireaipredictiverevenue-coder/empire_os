/** Source-backed homepage summary; reuses the existing NWS Atlas request. */
export function summarizeHomeSource(weather) {
  const empty = (phase,title,detail)=>({
    phase,title,detail,count:null,area:"Selected US area",checked_at:null
  });
  if(!weather||weather.kind==="loading")return empty(
    "loading","Checking official weather records",
    "Retrieving NWS information. No safety conclusion can be drawn yet."
  );
  if(weather.kind!=="ready")return empty(
    "unavailable","Official alerts unavailable",
    "The source could not be checked. Use weather.gov and local warning channels."
  );
  const data=weather.data;
  const count=data?.alert_count;
  const alerts=data?.alerts;
  const when=typeof data?.checked_at==="string"?Date.parse(data.checked_at):NaN;
  if(data?.source!=="National Weather Service"||!Number.isSafeInteger(count)||count<0||
    !Array.isArray(alerts)||alerts.length!==count||!Number.isFinite(when)) {
    return empty("unavailable","Weather records could not be verified",
      "Check the original National Weather Service source directly.");
  }
  const area=typeof data.area==="string"&&data.area.trim()?data.area.trim().slice(0,110):"Selected US area";
  return {
    phase:"available",count,area,checked_at:new Date(when).toISOString(),
    title:count===0?"No active alerts returned":count===1?"1 active alert returned":count+" active alerts returned",
    detail:count===0?
      "No records returned at the last check. That is not an all-clear.":
      "Official issued records for this area. Check coverage and expiry; warnings do not prove property damage."
  };
}
