/**
 * Evergreen, independently source-linked homeowner pathways.
 * No live-storm probability, property-damage inference, fabricated telemetry
 * or pressure-sale promises. This is a content navigation slider.
 */
export const STORM_JOURNEYS=Object.freeze([
  {
    id:"prepare",step:"01",label:"PREPARE",eyebrow:"BEFORE THE WEATHER CHANGES",
    title:"A little preparation",emphasis:"makes a difference.",
    description:"Make a plan for your household, check supplies, keep important documents accessible and know where official warnings will reach you.",
    actions:["Make a household contact plan","Check emergency supplies","Know your local warning channels"],
    primary:{label:"Your Storm Passport",href:"#passport"},
    secondary:{label:"Ready.gov preparation guide",href:"https://www.ready.gov/"},
    source:"FEMA / Ready.gov",tone:"prepare",
  },
  {
    id:"understand",step:"02",label:"UNDERSTAND",eyebrow:"WHEN CONDITIONS CHANGE",
    title:"Know what the",emphasis:"warning actually says.",
    description:"Read the National Weather Service alert, affected area and issue time. Check local authorities and follow safety instructions over any website visualisation.",
    actions:["Review the official warning","Check its area and expiry","Follow local safety advice"],
    primary:{label:"Check official alerts",href:"/alerts"},
    secondary:{label:"National Weather Service",href:"https://www.weather.gov/"},
    source:"NWS / weather.gov",tone:"understand",
  },
  {
    id:"recover",step:"03",label:"RECOVER",eyebrow:"WHEN IT IS SAFE TO RETURN",
    title:"Take the next step",emphasis:"at your own pace.",
    description:"Put safety first. Record what you can see without entering unsafe areas, keep useful records and review trustworthy recovery advice before arranging repairs.",
    actions:["Wait until the area is safe","Document observations carefully","Review recovery guidance"],
    primary:{label:"Explore recovery guidance",href:"/recovery"},
    secondary:{label:"FEMA recovery advice",href:"https://www.ready.gov/recovering-disaster"},
    source:"FEMA / Ready.gov",tone:"recover",
  },
]);
export function journeyIndex(current,delta,total=STORM_JOURNEYS.length){
  if(!Number.isInteger(current)||!Number.isInteger(delta)||!Number.isInteger(total)||total<1)throw new TypeError("valid index and length required");
  return ((current+delta)%total+total)%total;
}
