import Link from "next/link";
import { connection } from "next/server";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { getQuoraResearchReview, type QuoraResearchReview } from "@/lib/search-api";
import styles from "../analytics.module.css";

export const metadata = {
  title: "Quora Research | Empire AI Search Intelligence",
  robots: { index: false, follow: false },
};

function trusted(value: QuoraResearchReview | null): value is QuoraResearchReview {
  return !!value
    && value.schema_version === "empire.search_intelligence.quora_research.v1"
    && value.mode === "OBSERVE" && value.execution_authority === "NONE"
    && value.automated_posting_authorized === false
    && value.affiliate_links_authorized === false
    && value.external_requests_performed === false
    && value.production_writes === false
    && value.third_party_visits_first_party === false
    && Array.isArray(value.topics) && value.topic_count === value.topics.length
    && value.topic_count <= 64
    && !!value.vertical_topic_counts
    && ["roofing","hvac","solar","dental","legal","b2b"].every(
      key => Number.isInteger(value.vertical_topic_counts[key]) &&
        value.vertical_topic_counts[key] === value.topics.filter(x => x.vertical === key).length
    )
    && value.topics.every(x =>
      x.editorial_review_required === true &&
      x.answer_publication_state === "RESEARCH_ONLY" &&
      x.proposed_page_public_verified === false
    );
}

const VERTICALS = [
  {key:"roofing",label:"Roofing and replacement"},
  {key:"hvac",label:"HVAC and heat pumps"},
  {key:"solar",label:"Solar and battery storage"},
  {key:"dental",label:"Dental and patient decisions"},
  {key:"legal",label:"Legal service research"},
  {key:"b2b",label:"B2B growth and predictive revenue"},
] as const;

export default async function QuoraResearchDepartment() {
  await connection();
  // Follow the existing frozen private-agency SSH/loopback ingress boundary.
  // The header check is defence in depth; it is not independent user auth.
  if (process.env.EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED !== "1") {
    notFound();
  }
  const requestHeaders = await headers();
  const allowed = new Set(["127.0.0.1:3001", "localhost:3001"]);
  if (process.env.EMPIRE_QUORA_PREVIEW_LOOPBACK_PORT === "3109") {
    allowed.add("127.0.0.1:3109");
    allowed.add("localhost:3109");
  }
  const host = requestHeaders.get("host")?.toLowerCase() ?? "";
  const forwardedHost = requestHeaders.get("x-forwarded-host")?.toLowerCase();
  const forwardedFor = requestHeaders.get("x-forwarded-for");
  const nonLocalForwarding = forwardedFor !== null
    && !["127.0.0.1", "::1"].includes(forwardedFor.trim());
  const proxySignal = [
    "x-real-ip", "forwarded", "via", "cf-connecting-ip", "cf-ray",
  ].some(name => requestHeaders.has(name));
  if (!allowed.has(host) || (forwardedHost && !allowed.has(forwardedHost))
      || nonLocalForwarding || proxySignal) {
    notFound();
  }
  const response = await getQuoraResearchReview();
  const d = response.ok && trusted(response.data) ? response.data : null;
  return <main className={styles.analytics}>
    <div className={styles.workspace}>
      <section className={styles.hero}>
        <div>
          <span className={styles.overline}>EMPIRE SEARCH INTELLIGENCE / ANSWER DISCOVERY</span>
          <h1>Quora <span>Research Desk</span></h1>
          <p>Source-checked homeowner questions, existing SEO topics and editor-reviewed answers. No automated posting or invented buyer intent.</p>
          <div className={styles.heroMeta}><span className={styles.liveDot} aria-hidden="true"/><span>Private Search Intelligence · OBSERVE</span></div>
          <Link href="/department" className={styles.inlineLink}>← SEO Analytics</Link>
        </div>
        <div className={styles.heroMark} aria-hidden="true">Q<span>/</span>A</div>
      </section>
      {!d ? <section className={styles.platformCard} role="status">
        <h2>Quora evidence unavailable</h2>
        <p>Private Search Intelligence source did not pass its review-only contract. Nothing has been published.</p>
        <p>{response.reason ?? "Source verification incomplete"}</p>
      </section> : <>
        <section className={styles.statGrid} aria-label="Quora research metrics">
          <div className={styles.stat}><div className={styles.statHeading}>Topic briefs</div><div className={styles.statValue}>{d.topic_count}</div><p className={styles.statDetail}>Editorial ideas, not observed questions</p></div>
          <div className={styles.stat}><div className={styles.statHeading}>Search candidates</div><div className={styles.statValue}>{d.source_candidates_count}</div><p className={styles.statDetail}>Unverified results from Search Fabric</p></div>
          <div className={styles.stat}><div className={styles.statHeading}>Verified questions</div><div className={styles.statValue}>{d.verified_quora_questions}</div><p className={styles.statDetail}>Requires direct page review</p></div>
          <div className={styles.stat}><div className={styles.statHeading}>Published answers</div><div className={styles.statValue}>{d.published_answers_verified}</div><p className={styles.statDetail}>Not inferred from topic research</p></div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="quora-queue">
          <div className={styles.sectionLead}><div><span className={styles.overline}>01 / EDITORIAL QUEUE</span><h2 id="quora-queue">Questions worth researching</h2></div><span>HUMAN REVIEW REQUIRED</span></div>
          <div className={styles.platformCard}>
            <p className={styles.cardDescription}>These are 56 prepared topic hypotheses across six industries, not observed Quora questions. Verify each original question, answer substantively and disclose relevant affiliations. Do not link unpublished pages or route dental/legal research into the Lead Smart roofing buyer.</p>
            {VERTICALS.map(({key,label}) => <details key={key} open={key==="roofing"}>
              <summary><strong>{label}</strong> — {d.vertical_topic_counts[key]} question topics</summary>
              <ol className={styles.todoList}>
                {d.topics.filter(item=>item.vertical===key).map((item,i)=><li key={item.item_id}>
                  <span>{String(i+1).padStart(2, "0")}</span>
                  <div>
                    <strong>{item.question_theme}</strong>
                    <small>{item.item_id} · {item.intent_hypothesis.replaceAll("_", " ").toLowerCase()} · Research only</small>
                    <p>Precise query: <code>{item.source_query_plan}</code></p>
                    <p>Broader fallback: <code>{item.broader_discovery_query_plan}</code> — search candidate only</p>
                    <p>Draft destination: <code>{item.proposed_owned_page}</code> (not release-approved)</p>
                    {item.specialist_editorial_review_required && <p>Specialist legal or clinical editorial verification required before any answer.</p>}
                  </div>
                </li>)}
              </ol>
            </details>)}
          </div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="quora-gates">
          <div className={styles.sectionLead}><div><span className={styles.overline}>02 / SOURCE GOVERNANCE</span><h2 id="quora-gates">What is not proven</h2></div></div>
          <div className={styles.platformCard}>
            <p className={styles.cardDescription}>Actual Quora question pages, editorial sign-off, verified website visits, commercial enquiries and buyer revenue remain unproven. External Quora visits are not owned Google SEO clicks.</p>
            <p>Editorial approval: {d.owner_editorial_signoff_verified ? "observed" : "pending"}. Search Fabric and Google ranking signals are independent evidence sources; neither grants an advertising or affiliate-link permission.</p>
          </div>
        </section>
      </>}
      <footer className={styles.footer}>EMPIRE AI · QUORA RESEARCH | No automated posts, live buyer calls or sales claims.</footer>
    </div>
  </main>;
}
