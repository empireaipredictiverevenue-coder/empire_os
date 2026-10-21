/** Human readable, source-dated weather times with a supported Intl format.
 * Do not combine dateStyle/timeStyle and explicit timeZoneName: Chrome and Node reject it.
 */
const formatter = new Intl.DateTimeFormat("en-US", {
  year:"numeric",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short",
});
export function formatWeatherTime(value,missing="Time unavailable") {
  if(typeof value!=="string"||!value.trim())return missing;
  const date=new Date(value);
  return Number.isFinite(date.getTime())?formatter.format(date):missing;
}
