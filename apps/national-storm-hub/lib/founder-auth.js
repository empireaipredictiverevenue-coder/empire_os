import {createHash,timingSafeEqual} from "node:crypto";
export const FOUNDER_HEADERS={
  "Cache-Control":"private, no-store, max-age=0",
  "Vary":"Authorization",
  "X-Robots-Tag":"noindex, nofollow",
};
export function verifyFounderRequest(headers,secret=process.env.NSH_FOUNDER_PULSE_KEY){
  if(typeof secret!=="string"||secret.length<48)return "NOT_CONFIGURED";
  const bearer=headers?.get?.("authorization")||"";
  if(!bearer.startsWith("Bearer ")||bearer.length>260)return "UNAUTHORIZED";
  const candidate=bearer.slice(7);
  const expected=createHash("sha256").update(secret).digest();
  const actual=createHash("sha256").update(candidate).digest();
  return timingSafeEqual(expected,actual)?"AUTHORIZED":"UNAUTHORIZED";
}
