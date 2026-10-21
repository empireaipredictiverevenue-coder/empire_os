/** Three genuine customer journeys, not fabricated weather observations. */
export const HERO_STORIES=Object.freeze([
  {
    id:"intelligence",number:"01",kicker:"WEATHER INTELLIGENCE / SOURCE FIRST",
    lead:"When the weather changes,",emphasis:"know what matters.",
    description:"Explore the official forecast and active warnings in one place. Understand what the sources say—and what they cannot prove.",
    cta:"Explore Storm Predictor",href:"/predictor",secondary:"Check live alerts",secondaryHref:"/alerts",
    signal:"NWS + SPC",detail:"FORECAST / WARNING / EVIDENCE",
    scene:"front"
  },
  {
    id:"warnings",number:"02",kicker:"ALERTS / REAL INFORMATION",
    lead:"The warning is real.",emphasis:"Your clarity matters.",
    description:"Browse National Weather Service warnings by ZIP or state, check their original issue times and coverage, and prepare with confidence.",
    cta:"Open Storm Alerts",href:"/alerts",secondary:"View research sources",secondaryHref:"/research",
    signal:"OFFICIAL NWS",detail:"SOURCE-LINKED WARNINGS",
    scene:"bands"
  },
  {
    id:"passport",number:"03",kicker:"PREPARE / PROTECT / REMEMBER",
    lead:"A stronger plan starts",emphasis:"before the storm.",
    description:"Save your area, work through a household preparedness checklist and bookmark source-linked weather records. Your early Passport stays in this browser.",
    cta:"Open Storm Passport",href:"#passport",secondary:"Safety & recovery guide",secondaryHref:"/recovery",
    signal:"HOMEOWNER FIRST",detail:"PREPAREDNESS / LOCAL PREVIEW",
    scene:"terrain"
  }
]);
export const nextHeroIndex=(index,delta,length=HERO_STORIES.length)=>
  ((index+delta)%length+length)%length;
