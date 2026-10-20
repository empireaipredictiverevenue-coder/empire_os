/**
 * Educational, locally evaluated demand-to-buyer funnel.
 * All values are visitor-controlled assumptions; never an observed lead,
 * a connected call, a completed solar job or a payable customer event.
 */
export type SectorExplorer = "roofing" | "solar" | "b2b";
export type FunnelAssumptions = Readonly<{
  monthlyEnquiries: number;
  qualificationPct: number;
  buyerAcceptancePct: number;
  completionPct: number;
}>;

export const FUNNEL_EXAMPLE: Record<SectorExplorer, FunnelAssumptions> = {
  roofing: {monthlyEnquiries: 80, qualificationPct: 40, buyerAcceptancePct: 35, completionPct: 0},
  solar: {monthlyEnquiries: 80, qualificationPct: 35, buyerAcceptancePct: 30, completionPct: 25},
  b2b: {monthlyEnquiries: 100, qualificationPct: 30, buyerAcceptancePct: 20, completionPct: 0},
};

const limits = {
  monthlyEnquiries: 10000,
  qualificationPct: 100,
  buyerAcceptancePct: 100,
  completionPct: 100,
} as const;

/** Fail closed on invalid source values. Do not clamp away missing or impossible inputs. */
export function calculateSectorFunnel(
  sector: SectorExplorer,
  assumptions: FunnelAssumptions,
) {
  if (!(sector in FUNNEL_EXAMPLE)) throw Error("Unknown scenario sector");
  for (const key of Object.keys(limits) as Array<keyof FunnelAssumptions>) {
    const value = assumptions[key];
    if (!Number.isFinite(value) || value < 0 || value > limits[key]) {
      throw Error("Invalid hypothetical funnel input: "+key);
    }
  }
  const monthlyEnquiries = assumptions.monthlyEnquiries;
  const qualified = monthlyEnquiries * assumptions.qualificationPct / 100;
  const accepted = qualified * assumptions.buyerAcceptancePct / 100;
  const completed = sector === "solar"
    ? accepted * assumptions.completionPct / 100
    : null;
  return {
    monthlyEnquiries,
    qualified,
    accepted,
    completed,
    isIllustrative: true as const,
    buyerAcceptedEventVerified: false as const,
    actualRevenueVerified: false as const,
    customerRecordsUsed: false as const,
  };
}

export const FUNNEL_PRESETS: ReadonlyArray<{id:string;label:string;factor:number}> = [
  {id:"cautious",label:"Cautious",factor:0.5},
  {id:"example",label:"Example",factor:1},
  {id:"higher",label:"Higher",factor:1.5},
];

export function sectorPreset(sector:SectorExplorer, id:string): FunnelAssumptions {
  const preset = FUNNEL_PRESETS.find(item=>item.id===id);
  if(!preset) throw Error("Unknown example preset");
  const base = FUNNEL_EXAMPLE[sector];
  return {
    monthlyEnquiries: Math.round(base.monthlyEnquiries * preset.factor),
    qualificationPct: Math.min(100, Math.round(base.qualificationPct * preset.factor)),
    buyerAcceptancePct: Math.min(100, Math.round(base.buyerAcceptancePct * preset.factor)),
    completionPct: Math.min(100, Math.round(base.completionPct * preset.factor)),
  };
}
