/** Editorial hazard lenses with official sources. NOT real-time risk estimates. */
export const HAZARD_LENSES=Object.freeze([
  {id:"hail",index:"01",type:"HAIL / SEVERE WIND",
   title:"Watch the skies. Understand the signal.",
   summary:"Hail and severe-wind warnings describe an area of concern—not confirmed damage to your roof or property.",
   note:"Check the active warning, expected timing and safety instructions before acting.",
   label:"SPC convective outlooks",href:"https://www.spc.noaa.gov/products/outlook/",theme:"red"},
  {id:"flood",index:"02",type:"HEAVY RAIN / FLOODING",
   title:"Flood risk isn't one single line.",
   summary:"Local flash-flood warnings, river forecasts and longer-term flood maps explain different hazards and timescales.",
   note:"Never drive through flooded roads. Follow county and city emergency instructions.",
   label:"NWS flood safety",href:"https://www.weather.gov/safety/flood",theme:"yellow"},
  {id:"hurricane",index:"03",type:"HURRICANE / COASTAL",
   title:"Look beyond the forecast cone.",
   summary:"Hurricane-track uncertainty is not an impact boundary. Wind, storm surge and rainfall may affect areas outside the cone.",
   note:"Use official evacuation zones and local emergency-management instructions.",
   label:"National Hurricane Center",href:"https://www.nhc.noaa.gov/",theme:"white"},
  {id:"tornado",index:"04",type:"TORNADO / HIGH WIND",
   title:"Prepare a shelter plan in advance.",
   summary:"A tornado watch and warning have distinct meanings. Your safety plan should never depend on this website remaining open.",
   note:"Know your safest interior shelter area and follow official warnings.",
   label:"NWS tornado safety",href:"https://www.weather.gov/safety/tornado",theme:"red"}
]);
