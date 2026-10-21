import Link from "next/link";
import Image from "next/image";
import { connection } from "next/server";
import { getSeoDepartmentReview, type SeoDepartmentReview } from "@/lib/search-api";
import { ObservedGscTrend } from "./observed-trend";
import styles from "./analytics.module.css";

export const metadata = {
  title: "Empire Analytics | Predictive Revenue Intelligence",
  description: "Private, source-verified analytics for Empire AI.",
  robots: { index: false, follow: false },
};

type IconName = "overview" | "growth" | "pages" | "conversion" | "quality" | "research";

function Glyph({ name }: { name: IconName }) {
  const paths: Record<IconName, React.ReactNode> = {
    overview: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    growth: <><path d="m3 17 6-6 4 4 8-9"/><path d="M15 6h6v6"/></>,
    pages: <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/></>,
    conversion: <><path d="M3 12h7l3 3 8-9"/><path d="M15 6h6v6"/></>,
    quality: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
    research: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>,
  };
  return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

const MENU: Array<{label: string; href: string; icon: IconName}> = [
  { label: "Overview", href: "#overview", icon: "overview" },
  { label: "Acquisition", href: "#acquisition", icon: "growth" },
  { label: "Content & SEO", href: "#content", icon: "pages" },
  { label: "Conversions", href: "#conversions", icon: "conversion" },
  { label: "Data quality", href: "#data-quality", icon: "quality" },
];

function Stat({ label, value, detail, status, emphasis }: {
  label: string;
  value: string;
  detail: string;
  status?: string;
  emphasis?: boolean;
}) {
  return <div className={`${styles.stat} ${emphasis ? styles.statBright : ""}`}>
    <div className={styles.statHeading}>{label}<span className={styles.statMarker} aria-hidden="true" /></div>
    <div className={styles.statValue}>{value}</div>
    <p className={styles.statDetail}>{detail}</p>
    {status && <span className={styles.statStatus}>{status}</span>}
  </div>;
}

function Signal({ label, state, detail, good }: {
  label: string; state: string; detail: string; good: boolean;
}) {
  return <div className={styles.signal}>
    <span className={`${styles.signalDot} ${good ? styles.signalGood : styles.signalHeld}`} aria-hidden="true"/>
    <div><strong>{label}</strong><p>{detail}</p></div>
    <span className={styles.signalState}>{state}</span>
  </div>;
}

function UnknownMetric({ name, why }: { name: string; why: string }) {
  return <div className={styles.unknownMetric}>
    <span>{name}</span>
    <strong>Not connected</strong>
    <p>{why}</p>
  </div>;
}

const EXPLANATIONS: Record<string,string> = {
  ORGANIC_RELEASE_SOURCE_COMMIT_NOT_VERIFIED:"Reconcile the original release to its production source commit.",
  INDUSTRY_CAMPAIGN_RELEASE_NOT_VERIFIED:"Verify measured industry-campaign activity before attributing results.",
  HISTORIC_GSC_404_EDITORIAL_TRIAGE_PENDING:"Decide which legacy pages deserve genuine original editorial recovery.",
  SEMANTIC_ORIGINAL_CONTENT_EDITORIAL_REVIEW_PENDING:"Finish original HVAC and solar quality improvements.",
  INDEPENDENT_AI_ANSWER_CITATION_EVIDENCE_MISSING:"Capture external AI-answer citation evidence with source and timestamp.",
  INDEPENDENT_SERP_RANKING_OBSERVATIONS_NOT_VERIFIED_BY_THIS_REVIEW:"Obtain independently attested keyword rankings; GSC averages are not them.",
  ORGANIC_BUYER_ENQUIRY_AND_REALIZED_REVENUE_NOT_PROVEN:"Attribute a genuine first-party enquiry to an actual CRM and settlement receipt.",
  EDITORIAL_RESEARCH_REQUIRES_OWNER_PUBLICATION_DECISION:"Owner-review industry research before any public release.",
};

function RecoveryBars({ report }: {report: SeoDepartmentReview}) {
  const counts = [
    { name:"Empire product", count:report.legacy_404_editorial_category_counts.EMPIRE_PRODUCT_TOPIC_REVIEW ?? 0, tone:"blue"},
    { name:"Roofing research", count:report.legacy_404_editorial_category_counts.ROOFING_RESEARCH_REVIEW ?? 0, tone:"gold"},
    { name:"Buyer intent", count:report.legacy_404_editorial_category_counts.BUYER_INTENT_EDITORIAL_REVIEW ?? 0, tone:"cyan"},
    { name:"Off-core retained 404", count:report.legacy_404_editorial_category_counts.OFF_CORE_RETAIN_404_PENDING_EVIDENCE ?? 0, tone:"grey"},
  ];
  const maximum = Math.max(1,...counts.map(x=>x.count));
  return <div className={styles.recoveryBars} role="group" aria-label="Verified 404 URL editorial category counts">
    {counts.map(row=><div key={row.name} className={styles.barRow}>
      <span>{row.name}</span>
      <div className={styles.barTrack}>
        <div className={styles.barFill} data-tone={row.tone} style={{width:`${100*row.count/maximum}%`}} />
      </div>
      <strong>{row.count}</strong>
    </div>)}
  </div>;
}

function Workspace({ report: d }: { report: SeoDepartmentReview }) {
  const chart = d.gsc_daily_chart;
  const observed = chart?.status === "DATE_DIMENSION_ROWS_OBSERVED"
    && chart.reported_date_dimension_impressions !== null
    && chart.reported_date_dimension_clicks !== null
    && chart.days_observed !== null;
  const impressions = observed ? chart.reported_date_dimension_impressions! : null;
  const clicks = observed ? chart.reported_date_dimension_clicks! : null;
  const display = (n: number | null) => n === null ? "—" : n.toLocaleString("en-GB");
  const ctr = impressions !== null && clicks !== null && impressions > 0
    ? `${(clicks/impressions*100).toFixed(2)}%` : "—";
  const statusWindow = chart?.date_window?.join(" — ") || d.gsc_final_page_window.join(" — ");

  return <>
    <section id="overview" className={styles.hero} aria-labelledby="analytics-title">
      <div>
        <span className={styles.overline}>INTELLIGENCE / FIRST-PARTY ANALYTICS</span>
        <h1 id="analytics-title">Analytics <span>Command Centre</span></h1>
        <p>From visibility to verified revenue. Performance, acquisition, commercial signals and source integrity—one accountable view.</p>
        <div className={styles.heroMeta}>
          <span className={styles.liveDot}/><span>Observed source data</span><span className={styles.metaSeparator} aria-hidden="true"/>
          <span>GSC reporting window: {statusWindow}</span>
        </div>
      </div>
      <div className={styles.heroMark} aria-hidden="true">E<span>/</span>A</div>
    </section>
    <div className={styles.sectionLead}><h2>Performance snapshot</h2><span>Google Search Console · DATE DIMENSION</span></div>
    <section aria-label="Observed acquisition measurements" className={styles.statGrid}>
      <Stat label="Search impressions" value={display(impressions)} detail="Date-dimension GSC reports; not website visits." status={observed?"Source observed":"Source unavailable"} emphasis/>
      <Stat label="Organic search clicks" value={display(clicks)} detail="Clicks reported by the same date-dimension source." status={observed?"Source observed":"Source unavailable"}/>
      <Stat label="Search click-through" value={ctr} detail="Derived only from date-dimension reported clicks ÷ impressions." status={observed?"Calculated from source":"Unavailable"}/>
      <Stat label="Observed dates" value={display(observed?chart.days_observed:null)} detail={observed?`${chart.days_missing_unreported?.length ?? "?"} dates unreported in this window`:"Awaiting source observations"} status="Not a sitewide traffic total"/>
    </section>

    <section id="acquisition" className={styles.analyticsSection} aria-labelledby="acquisition-title">
      <div className={styles.sectionLead}><div><span className={styles.overline}>01 / ACQUISITION</span><h2 id="acquisition-title">Search performance</h2></div>
        <span>GSC DATA · NOT SESSION ANALYTICS</span></div>
      <ObservedGscTrend chart={chart} />
      <div className={styles.panelFoot}>Google Search Console average position is a property-level aggregate, not an independently verified, locale-specific keyword ranking. No estimated clicks or fabricated days.</div>
    </section>

    <section id="content" className={styles.analyticsSection} aria-labelledby="content-title">
      <div className={styles.sectionLead}><div><span className={styles.overline}>02 / CONTENT INTELLIGENCE</span><h2 id="content-title">SEO recovery & search coverage</h2></div><Link href="/department/evidence" className={styles.inlineLink}>Detailed evidence <span aria-hidden="true">↗</span></Link></div>
      <div className={styles.twoColumns}>
        <div className={styles.platformCard}>
          <div className={styles.cardTitle}><h3>Historical 404 portfolio</h3><span>{d.legacy_missing_404_count_in_returned_page_sample} sample rows</span></div>
          <p className={styles.cardDescription}>Actions by genuine editorial relevance, not automatic redirects or simulated recovery.</p>
          <RecoveryBars report={d}/>
          <div className={styles.cardFoot}>
            <span><strong>{d.legacy_404_core_topic_editorial_review_count}</strong> core-topic reviews</span>
            <span><strong>{d.legacy_404_off_core_retain_404_count}</strong> off-core remain retired</span>
          </div>
        </div>
        <div className={styles.platformCard}>
          <div className={styles.cardTitle}><h3>Page-dimension report</h3><span>Separate GSC slice</span></div>
          <p className={styles.cardDescription}>This is a sampled set of URL-level rows. Do not add it to the date-dimension metrics above.</p>
          <div className={styles.miniGrid}>
            <Stat label="Page rows" value={display(d.gsc_returned_page_rows)} detail="Returned GSC URL rows"/>
            <Stat label="Page impressions" value={display(d.gsc_returned_page_sample_impressions)} detail="Page sample only"/>
            <Stat label="Page clicks" value={display(d.gsc_returned_page_sample_clicks)} detail="Page sample only"/>
            <Stat label="404 impressions" value={display(d.legacy_missing_404_impressions_in_returned_page_sample)} detail="Historical URLs in sample"/>
          </div>
        </div>
      </div>
    </section>

    <section id="conversions" className={styles.analyticsSection} aria-labelledby="conversion-title">
      <div className={styles.sectionLead}><div><span className={styles.overline}>03 / COMMERCIAL ATTRIBUTION</span><h2 id="conversion-title">Visitor-to-revenue journey</h2></div><Link href="/founder/commercial-pipeline" className={styles.inlineLink}>Commercial Operations <span aria-hidden="true">↗</span></Link></div>
      <div className={styles.platformCard}>
        <p className={styles.cardDescription}>A full analytics platform needs first-party sessions and consent-aware events, then a verified CRM and payment join. We will not substitute GSC impressions for visitors or revenue.</p>
        <div className={styles.unknownGrid}>
          <UnknownMetric name="Visitors & sessions" why="First-party visit/session collection not yet verified."/>
          <UnknownMetric name="Engaged sessions" why="Consent-aware page and engagement events are not connected."/>
          <UnknownMetric name="Conversion rate" why="Requires observed sessions and confirmed conversion events."/>
          <UnknownMetric name="Attributed revenue" why="Requires source-linked CRM, buyer and settlement receipts."/>
        </div>
        <div className={styles.conversionFlow}>
          <span>Acquisition <small>GSC observed</small></span><b aria-hidden="true">→</b>
          <span>Visitor <small>Not connected</small></span><b aria-hidden="true">→</b>
          <span>Enquiry <small>Not proven</small></span><b aria-hidden="true">→</b>
          <span>Revenue <small>Not proven</small></span>
        </div>
      </div>
    </section>

    <section id="data-quality" className={styles.analyticsSection} aria-labelledby="quality-title">
      <div className={styles.sectionLead}><div><span className={styles.overline}>04 / GOVERNANCE & SOURCE HEALTH</span><h2 id="quality-title">Measurement integrity</h2></div><span>{d.open_gates.length} open evidence gates</span></div>
      <div className={styles.twoColumns}>
        <div className={styles.platformCard}>
          <div className={styles.cardTitle}><h3>Source availability</h3><span>LIVE / READ-ONLY</span></div>
          <Signal label="Google Search Console" state={observed?"Observed":"Held"} detail="First-party date-dimension rows" good={observed}/>
          <Signal label="Owned site routes" state={d.semantic_owned_pages_commercial_route_verified?"Observed":"Not verified"} detail={`${d.semantic_live_priority_pages_checked} owned priority pages checked`} good={d.semantic_owned_pages_commercial_route_verified}/>
          <Signal label="Search Fabric cache" state="Diagnostic only" detail={`${d.search_fabric_cache_fresh_candidates_24h} fresh / ${d.search_fabric_cache_stale_candidates} stale / ${d.search_fabric_cache_invalid_envelopes} invalid envelopes`} good={false}/>
          <Signal label="Independent rankings" state="Not verified" detail="Cached SERPs and GSC averages do not prove ranks" good={false}/>
          <Signal label="AI answer citations" state={d.external_ai_answer_citation_verified?"Observed":"Not verified"} detail="Requires independently sourced answer captures" good={d.external_ai_answer_citation_verified}/>
        </div>
        <div className={styles.platformCard}>
          <div className={styles.cardTitle}><h3>Prioritised open work</h3><span>{d.open_gates.length} gates</span></div>
          <ol className={styles.todoList}>
            {d.open_gates.map((gate,i)=><li key={gate}>
              <span>{String(i+1).padStart(2,"0")}</span>
              <div><strong>{EXPLANATIONS[gate]??"Review source and evidence gate"}</strong>
                <small>{gate.replaceAll("_"," ").toLowerCase()}</small></div>
            </li>)}
          </ol>
        </div>
      </div>
    </section>
  </>;
}

const NAV: Array<{label:string; href:string; icon:IconName}>=[
  ...MENU,
  {label:"Quora research",href:"/department/quora",icon:"research"},
  {label:"Raw evidence",href:"/department/evidence",icon:"research"},
];

export default async function AnalyticsDepartment() {
  await connection();
  const response = await getSeoDepartmentReview();
  const d = response.ok ? response.data : null;
  const trusted = d?.schema_version === "empire.search_growth.department_integration.v1"
    && d.mode === "OBSERVE" && d.execution_authority === "NONE"
    && d.customer_identifiers_disclosed === false
    && d.publisher_mutation_authorized === false;
  return <main className={styles.analytics}>
    <div className={styles.workspace}>
      <aside className={styles.sidebar} aria-label="Empire Analytics sections">
        <Link href="/department" className={styles.brand} aria-label="Empire AI Analytics overview">
          <Image src="/brand/empire-ai-official-brand-logo-lockup.png" alt="Empire AI Predictive Revenue" width={100} height={76} className={styles.brandImage} priority/>
          <div><strong>EMPIRE <span>AI</span></strong><small>ANALYTICS INTELLIGENCE</small></div>
        </Link>
        <div className={styles.sideCategory}>WORKSPACE</div>
        <nav className={styles.sideNav}>
          {NAV.map((item,i)=><Link key={item.href} href={item.href} className={i===0?styles.sideSelected:styles.sideLink}>
            <Glyph name={item.icon}/><span>{item.label}</span>{i===0&&<span className={styles.currentMarker}/>}
          </Link>)}
        </nav>
        <div className={styles.sideSpacer}/>
        <div className={styles.sideFooter}>
          <span className={styles.smallPulse} aria-hidden="true"/> LIVE SOURCE · OBSERVE MODE
          <p>Private analytics workspace, no publishing or outbound authority.</p>
        </div>
      </aside>
      <div className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.breadcrumb}>EMPIRE OS <span>/</span> INTELLIGENCE <span>/</span> <strong>ANALYTICS</strong></div>
          <div className={styles.topActions}>
            <span className={styles.readOnly}>READ-ONLY</span>
            <Link href="/founder" className={styles.topLink}>Founder Console ↗</Link>
          </div>
        </header>
        <div className={styles.mobileNav}><nav aria-label="Analytics mobile navigation">{NAV.map(item=><Link key={item.href} href={item.href}>{item.label}</Link>)}</nav></div>
        <div className={styles.body}>
          {!trusted || !d ?
            <section role="status" className={styles.platformCard}>
              <p className={styles.overline}>SOURCE STATUS</p><h1>Analytics data unavailable</h1>
              <p>Private Search Intelligence has not returned a verified aggregate. No visits, clicks, rankings or conversions have been guessed.</p>
              <small>{response.status===503?"Source review held":response.reason??"Server-only source connection pending"}</small>
            </section> :
            <Workspace report={d}/>}
          <footer className={styles.footer}>EMPIRE AI · PREDICTIVE REVENUE | First-party measured data only. Not Google Analytics; sessions, event telemetry and customer attribution remain subject to verified integration and approval.</footer>
        </div>
      </div>
    </div>
  </main>;
}
