import Link from "next/link";
import { connection } from "next/server";
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
    && value.topic_count <= 64;
}

export default async function QuoraResearchDepartment() {
  await connection();
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
            <p className={styles.cardDescription}>These are prepared research queries. Before answering, verify that a genuine Quora question exists, read it in context, and produce a useful original answer. Do not link unpublished homeowner guides.</p>
            <ol className={styles.todoList}>
              {d.topics.map((item,i)=><li key={item.item_id}>
                <span>{String(i+1).padStart(2, "0")}</span>
                <div>
                  <strong>{item.question_theme}</strong>
                  <small>{item.item_id} · {item.intent_hypothesis.replaceAll("_", " ").toLowerCase()} · Research only</small>
                  <p>Search plan: <code>{item.source_query_plan}</code></p>
                  <p>Draft guide: <code>{item.proposed_owned_page}</code> (not release-approved)</p>
                </div>
              </li>)}
            </ol>
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
