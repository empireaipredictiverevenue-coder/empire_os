/** Original, bounded local utility for the first two regional Storm Hub pilots. */
export const STATE_HUBS = Object.freeze({
  texas: {
    name:"Texas Storm Hub", code:"TX", category:"Hail · Wind · Flash Flooding", eyebrow:"THE LONE STAR WEATHER CORRIDOR",
    headline:"Severe weather deserves a clearer picture.",
    intro:"From North Texas thunderstorm and hail seasons to Gulf Coast wind and inland flash flooding, weather preparedness depends on your community and the official warning in effect.",
    themes:[
      {title:"Hail & severe thunderstorms",body:"Review official watches and warnings and check vehicle and outdoor-item protection plans well before severe conditions arrive."},
      {title:"Flash flooding",body:"Know safer routes and local alerts. Never enter or drive through floodwater; conditions can change quickly."},
      {title:"After severe wind",body:"Stay clear of downed lines and unstable structures. Record observations only when authorities say it is safe."},
    ],
    steps:[
      "Identify a secure indoor area away from windows for severe thunderstorms.",
      "Review local flood-prone roads and safer evacuation options.",
      "Maintain a household communication and emergency kit.",
      "Check the latest county or city emergency management information.",
    ],
    sources:[
      {name:"Texas Division of Emergency Management",href:"https://www.tdem.texas.gov/"},
      {name:"NOAA Storm Prediction Center",href:"https://www.spc.noaa.gov/"},
      {name:"National Weather Service",href:"https://www.weather.gov/"},
    ],
    explanation:"The Texas preview prioritises hail, strong wind and flood preparedness, with official public-source evidence and no implied property-damage verdict.",
  },
  florida: {
    name:"Florida Storm Hub",code:"FL",category:"Hurricanes · Flooding · Coastal Conditions",eyebrow:"THE SUNSHINE STATE WEATHER CORRIDOR",
    headline:"Prepare before the forecast becomes urgent.",
    intro:"Florida households need location-specific hurricane and flood plans. Evacuation zones, shelter options, rain, surge and wind risks vary greatly by location and construction type.",
    themes:[
      {title:"Hurricane readiness",body:"Know your local evacuation zone and official route before a storm is approaching. Follow local emergency management directions."},
      {title:"Heavy rain & flooding",body:"Understand that inland rainfall flooding and coastal surge are different hazards. Never drive into flooded roads."},
      {title:"Power and household planning",body:"Review plans for medication, pets, reliable communications and safe generator use well ahead of hurricane season."},
    ],
    steps:[
      "Find your official county evacuation zone and nearby shelter guidance.",
      "Prepare household supplies, medication arrangements and pet care plans.",
      "Keep insurance and essential documents in a secure, accessible location.",
      "Follow the National Hurricane Center and local emergency management office.",
    ],
    sources:[
      {name:"Florida Division of Emergency Management",href:"https://www.floridadisaster.org/planprepare/"},
      {name:"National Hurricane Center",href:"https://www.nhc.noaa.gov/"},
      {name:"National Weather Service",href:"https://www.weather.gov/"},
    ],
    explanation:"This Florida preview focuses on storm readiness and authoritative evacuation guidance. It does not provide insurance-claim advice or sell repair referrals.",
  },
});
export function getStateHub(slug) {return Object.hasOwn(STATE_HUBS,slug)?STATE_HUBS[slug]:null;}
