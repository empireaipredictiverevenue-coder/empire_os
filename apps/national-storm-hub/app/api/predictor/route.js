import {NextResponse} from "next/server";
import {normalizeZip,geocodeFromZippopotam,nwsAlertUrl,normalizeAlerts} from "../../../lib/storm-data.js";
import {normalizePeriods,verifiedForecastUrl,spcQueryUrl,normalizeSpc,summarizePredictor} from "../../../lib/predictor.js";
import {reviewOfficialWeatherIntelligence} from "../../../lib/storm-intelligence-bridge.js";
export const dynamic="force-dynamic";
const BASE_HEADERS={"Cache-Control":"no-store"};
const AGENT=process.env.STORM_HUB_NWS_USER_AGENT||"NationalStormHub/0.2 (https://nationalstormhub.com)";
async function getJSON(url,{noaa=false}={}){
  const r=await fetch(url,{
    headers:{"Accept":"application/geo+json, application/json",...(noaa?{"User-Agent":AGENT}:{})},
    next:{revalidate:300},
    signal:AbortSignal.timeout(8500)
  });
  if(!r.ok)throw new Error("UPSTREAM_STATUS_"+r.status);
  return r.json();
}
export async function GET(req){
  const zip=new URL(req.url).searchParams.get("zip");
  if(!normalizeZip(zip))return NextResponse.json({error:"Enter a valid five-digit US ZIP."},{status:400,headers:BASE_HEADERS});
  let location;
  try{
    const geo=await getJSON("https://api.zippopotam.us/us/"+zip);
    location=geocodeFromZippopotam(geo,zip);
  }catch{
    return NextResponse.json({status:"LOCATION_UNAVAILABLE",error:"The ZIP location couldn't be verified."},{status:503,headers:BASE_HEADERS});
  }
  const now=new Date().toISOString();
  const result={
    schema_version:"nsh.predictor.v1",
    area:{zip:location.zip,name:location.name,state:location.state,method:"ZIP_CENTROID"},
    checked_at:now,
    mode:"READ_ONLY",
    disclaimer:"Not an official alert service or individual property-damage forecast. Monitor NWS and local authorities.",
    alerts:{status:"UNAVAILABLE",items:[],checked_at:now,source:"https://api.weather.gov/alerts/active"},
    forecast:{status:"UNAVAILABLE",periods:[],source:"https://api.weather.gov/",checked_at:now},
    spc:{status:"UNAVAILABLE",category:null,source:"https://www.spc.noaa.gov/products/outlook/",checked_at:now},
  };
  // Independent failures never convert a failed source into a reassuring 'no risk' or 'all clear'.
  const tasks=[
    (async()=>{
      try{
        const nws=await getJSON(nwsAlertUrl({latitude:location.latitude,longitude:location.longitude}),{noaa:true});
        result.alerts={...result.alerts,status:"AVAILABLE",items:normalizeAlerts(nws)};
      }catch{result.alerts.status="UNAVAILABLE";}
    })(),
    (async()=>{
      try{
        const metadata=await getJSON(`https://api.weather.gov/points/${location.latitude.toFixed(4)},${location.longitude.toFixed(4)}`,{noaa:true});
        const link=verifiedForecastUrl(metadata);
        const forecast=await getJSON(link,{noaa:true});
        result.forecast={...result.forecast,status:"AVAILABLE",source:link,periods:normalizePeriods(forecast),
          generated_at:typeof forecast?.properties?.generatedAt==="string"?forecast.properties.generatedAt:null};
      }catch{result.forecast.status="UNAVAILABLE";}
    })(),
    (async()=>{
      const url=spcQueryUrl(location.latitude,location.longitude);
      if(!url){result.spc.status="OUTSIDE_CONUS_COVERAGE";return;}
      try{
        const spc=normalizeSpc(await getJSON(url));
        result.spc.status="AVAILABLE";
        result.spc.category=spc;
      }catch{result.spc.status="UNAVAILABLE";}
    })()
  ];
  await Promise.all(tasks);
  const good=[result.alerts.status,result.forecast.status,result.spc.status].filter(x=>x==="AVAILABLE").length;
  result.status=good===0?"SOURCES_UNAVAILABLE":good===3?"VERIFIED_SOURCES_RESPONDED":"PARTIAL_SOURCES_RESPONDED";
  result.predictor=summarizePredictor({
    alerts:result.alerts.items,periods:result.forecast.periods,spc:result.spc.category
  });
  // Reuse the same three original-source lookups: no second poller and no model-generated
  // homeowner, storm damage or commercial demand inference.
  result.intelligence=reviewOfficialWeatherIntelligence(result);
  return NextResponse.json(result,{status:good===0?503:200,headers:BASE_HEADERS});
}
