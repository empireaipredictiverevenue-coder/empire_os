import Link from "next/link";
import { connection } from "next/server";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import {
  getQuoraResearchReview, getQuoraJevShadowReview, getSeoJevDepartmentReview,
  getJevRealPilotReceipt, getJevOriginalPageEvidenceSummary, getSeoAiFirstSummary, getJevCaseModelSummary, getJevSeoDeploymentSummary,
  type QuoraResearchReview, type QuoraJevShadowReview, type SeoJevDepartmentReview,
  type JevRealPilotReceipt, type JevOriginalPageEvidenceSummary, type SeoAiFirstSummary, type JevCaseModelSummary, type JevSeoDeploymentSummary,
} from "@/lib/search-api";
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

function trustedJev(
  value: QuoraJevShadowReview | null, count: number,
): value is QuoraJevShadowReview {
  return !!value
    && value.schema_version === "empire.search.quora_jev_shadow_readiness.v1"
    && value.mode === "OBSERVE" && value.execution_authority === "NONE"
    && value.provider_key === "disabled" && value.provider_invoked === false
    && value.external_requests_performed === false && value.external_tokens_billed === 0
    && value.jev_model_predictions_count === 0
    && value.cases_ready_for_model_evaluation === 0
    && value.real_labeled_case_count === 0
    && value.reviewed_topics_count === count
    && value.publishing_authorized === false && value.buyer_routing_authorized === false
    && value.production_writes === false
    && value.typed_decision_task_readiness.promotion_review_ready === false
    && value.jev_use_case_readiness.provider_activation === false;
}

function trustedDepartment(
  value: SeoJevDepartmentReview | null,
): value is SeoJevDepartmentReview {
  return !!value
    && value.schema_version === "empire.search.jev_department_portfolio.v1"
    && value.mode === "OBSERVE"
    && value.scope === "EXISTING_SEO_DEPARTMENT"
    && value.execution_authority === "NONE"
    && value.jev_provider === "disabled"
    && value.jev_inference_calls === 0 && value.jev_scores_generated === 0
    && value.independent_case_evaluation_ready_count === 0
    && value.external_requests_performed_by_review === false
    && value.provider_keys_accessed === false
    && value.typed_decision_plan_only === true
    && value.database_writes === false && value.publication_authority === false
    && value.buyer_outreach_authority === false && value.payment_authority === false
    && value.task_count <= 20 && Array.isArray(value.task_board)
    && value.task_board.length === value.task_count
    && value.task_board.every(x =>
       x.jev_prediction === null && x.jev_score === null
       && x.model_evaluation_authorized === false
       && x.automatic_execution_authorized === false
       && x.publishing_authorized === false
    );
}

function trustedPilot(value: JevRealPilotReceipt | null):
  value is JevRealPilotReceipt {
  return !!value
    && value.schema_version === "empire.search.jev_one_shot_private_receipt_review.v1"
    && value.mode === "ONE_SHOT_SHADOW_ONLY"
    && value.provider_key === "openrouter_typesafe_jev"
    && value.model.startsWith("typesafe/jev-1.13")
    && value.actual_jev_inference_calls_observed === 1
    && value.execution_authority === "NONE"
    && value.provider_enabled_for_unattended_runs === false
    && value.new_provider_calls_triggered === 0
    && value.independent_eval_cases_ready === 0
    && value.accuracy_or_ground_truth_verified === false
    && value.publication_authorized === false
    && value.outreach_or_payment_authorized === false
    && value.database_writes === false
    && value.usage_cost_usd >= 0 && value.usage_cost_usd <= 0.0005
    && value.human_review_yes_probability >= 0
    && value.human_review_yes_probability <= 1;
}

function trustedOriginalIntake(value: JevOriginalPageEvidenceSummary | null):
  value is JevOriginalPageEvidenceSummary {
  return !!value && value.schema_version === "empire.search.jev_original_page_review_summary.v1"
    && value.mode === "OBSERVE" && value.execution_authority === "NONE"
    && value.reviewed_human_labels === 0 && value.benchmark_ready_cases === 0
    && value.authenticated_human_review_required === true
    && value.original_page_evidence_required === true
    && value.training_rights_verified === false
    && value.case_details_exposed === false
    && value.automatic_model_calls === false
    && value.publication_authority === false
    && value.provider_inference_from_status_read === false
    && value.observed_url_case_count >= 1 && value.observed_url_case_count <= 250
    && value.proposed_jev_model_outputs === 0
    && value.external_requests_performed === false
    && value.database_writes === false;
}

function trustedAiFirst(value: SeoAiFirstSummary | null):
  value is SeoAiFirstSummary {
  return !!value && value.schema_version === "empire.search.ai_first_seo_summary.v1"
    && value.mode === "OBSERVE" && value.execution_authority === "NONE"
    && value.observed_cases_reviewed === 30 && value.local_model_inference_attempts === 30
    && value.model_candidates_returned >= 0 && value.model_candidates_returned <= 30
    && value.deep_ai_research_queue_count >= 0 && value.deep_ai_research_queue_count <= 30
    && value.human_labels_created === 0
    && value.benchmark_accuracy_measured === false
    && value.original_content_verified === false
    && value.automatic_jev_inference_enabled === false
    && value.external_paid_jev_calls === 0
    && value.source_paths_exposed === false && value.publication_authority === false
    && value.shadow_model === "convaiinnovations/laya:onnx"
    && value.provider === "existing_local_laya_http"
    && value.model_output_status === "UNVERIFIED_RESEARCH_CANDIDATES"
    && value.receipt_read_calls_to_model === 0;
}

function trustedJevCases(value: JevCaseModelSummary | null):
  value is JevCaseModelSummary {
  return !!value
    && value.schema_version === "empire.search.jev_original_page_case_summary.v1"
    && value.mode === "REAL_PROVIDER_EVALUATION_SHADOW"
    && value.provider_key === "openrouter_typesafe_jev"
    && value.verified_provider_batches === 6
    && value.original_page_cases_assessed === 30
    && value.validated_model_responses === 30
    && value.model_confidence_at_least_0_80 + value.model_confidence_below_0_80 === 30
    && value.reported_cost_usd >= 0 && value.reported_cost_usd <= 0.006
    && value.model_prediction_accuracy_verified === false
    && value.original_page_copy_verified === false
    && value.model_outputs_are_human_labels === false
    && value.model_research_recommendations_are_authorised_fixes === false
    && value.unattended_provider_calls_enabled === false
    && value.new_inference_requests_during_status === 0
    && value.external_buyer_or_personal_data_sent === false
    && value.case_url_paths_exposed === false
    && value.manual_publication_or_redirect_authority === false
    && value.execution_authority === "NONE";
}

function trustedDeployment(value: JevSeoDeploymentSummary | null):
  value is JevSeoDeploymentSummary {
  return !!value && value.schema_version === "empire.search.jev_organic_deployment_summary.v1"
    && value.mode === "RESEARCH_TO_RELEASE_READY" && value.execution_authority === "NONE"
    && value.original_url_observations === 30 && value.jev_predictions_observed === 30
    && value.core_topic_research_observations === 15 && value.off_core_urls_retained_404 === 15
    && value.sample_page_impressions === 44 && value.sample_page_clicks === 0
    && value.website_changes_live === false && value.first_party_source_content_verified === false
    && value.seo_traffic_lift_verified === false && value.qualified_leads_verified === false
    && value.realised_revenue_verified === false && value.model_calls_during_summary === 0
    && value.personal_data_or_paths_disclosed === false
    && value.automatic_publishing_or_redirects_authorised === false
    && value.per_case_urls_exposed === false
    && value.publication_approval_required === true && value.redirect_approval_required === true
    && value.new_calls_or_billing_triggered === 0
    && Array.isArray(value.research_workstreams)
    && value.research_workstreams.length === 4
    && value.research_workstreams.reduce((n, x) => n + x.case_count, 0) === 30;
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
  const [response, jevResponse, departmentResponse, pilotResponse, intakeResponse, aiResponse, jevCasesResponse, deployResponse] = await Promise.all([
    getQuoraResearchReview(), getQuoraJevShadowReview(), getSeoJevDepartmentReview(),
    getJevRealPilotReceipt(), getJevOriginalPageEvidenceSummary(), getSeoAiFirstSummary(),
    getJevCaseModelSummary(), getJevSeoDeploymentSummary(),
  ]);
  const d = response.ok && trusted(response.data) ? response.data : null;
  const jev = d && jevResponse.ok && trustedJev(jevResponse.data, d.topic_count)
    ? jevResponse.data : null;
  const department = departmentResponse.ok && trustedDepartment(departmentResponse.data)
    ? departmentResponse.data : null;
  const pilot = pilotResponse.ok && trustedPilot(pilotResponse.data)
    ? pilotResponse.data : null;
  const intake = intakeResponse.ok && trustedOriginalIntake(intakeResponse.data)
    ? intakeResponse.data : null;
  const ai = aiResponse.ok && trustedAiFirst(aiResponse.data)
    ? aiResponse.data : null;
  const jevCases = jevCasesResponse.ok && trustedJevCases(jevCasesResponse.data)
    ? jevCasesResponse.data : null;
  const deployment = deployResponse.ok && trustedDeployment(deployResponse.data)
    ? deployResponse.data : null;
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
        <section className={styles.analyticsSection} aria-labelledby="quora-jev">
          <div className={styles.sectionLead}>
            <div><span className={styles.overline}>01 / TYPED DECISION INTELLIGENCE</span>
              <h2 id="quora-jev">Jev readiness</h2></div>
            <span>READ ONLY · NO PROVIDER CALL</span>
          </div>
          <div className={styles.platformCard}>
            {jev ? <>
              <p className={styles.cardDescription}>The existing Jev decision contracts cover {jev.reviewed_topics_count} research topics. This is an evidence-readiness check, not a Jev prediction or performance benchmark.</p>
              <p>Real labelled Quora cases: <strong>{jev.real_labeled_case_count}</strong> · Quora-specific Jev evaluations: <strong>{jev.jev_model_predictions_count}</strong> · Model evaluation ready: <strong>No</strong></p>
              <p>Evidence blockers: {jev.typed_decision_task_readiness.blockers.map(x => x.replaceAll("_"," ").toLowerCase()).join(" · ")}</p>
              <p>No automatic publication, outbound or third-party AI spending. Original Quora questions and independently reviewed labels are required before model evaluation.</p>
            </> : <p className={styles.cardDescription}>Jev evidence readiness is not independently available. No model activation or inference is assumed.</p>}
          </div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="seo-jev-real">
          <div className={styles.sectionLead}><div>
            <span className={styles.overline}>02 / VERIFIED INFERENCE</span>
            <h2 id="seo-jev-real">Jev model pilot</h2>
          </div><span>ONE EXTERNAL CALL · NO REPLAY</span></div>
          <div className={styles.platformCard}>
            {pilot ? <>
              <p className={styles.cardDescription}>Actual TypeSafe Jev inference observed through our existing OpenRouter gateway. One manual, tightly capped call evaluated aggregate legacy-404 Search Console evidence; this is not verified decision accuracy.</p>
              <p>Model: <code>{pilot.model}</code> · Decision: <strong>{pilot.decision_label.replaceAll("_"," ").toLowerCase()}</strong> · Confidence: <strong>{(pilot.decision_confidence*100).toFixed(0)}%</strong></p>
              <p>Human review yes-probability: <strong>{(pilot.human_review_yes_probability*100).toFixed(0)}%</strong> · Input tokens: <strong>{pilot.usage_input_tokens}</strong> · Observed cost: <strong>${pilot.usage_cost_usd.toFixed(6)}</strong></p>
              <p>Automatic Jev calls remain off. The result cannot approve redirects, publishing, buyer outreach, revenue or payments.</p>
            </> : <p className={styles.cardDescription}>An independently validated Jev inference receipt is not available. Do not assume paid model use or prediction accuracy.</p>}
          </div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="seo-jev-original-evidence">
          <div className={styles.sectionLead}><div>
            <span className={styles.overline}>03 / HUMAN EVALUATION DATASET</span>
            <h2 id="seo-jev-original-evidence">Original URL review intake</h2>
          </div><span>PRIVATE EVIDENCE · NO MODEL REQUEST</span></div>
          <div className={styles.platformCard}>
            {intake ? <>
              <p className={styles.cardDescription}>We recovered <strong>{intake.observed_url_case_count} deduplicated original owned-URL observations</strong> in a private, source-checked GSC review queue. These represent {intake.observed_impressions_from_sample} impressions in the sampled page window, not sitewide visits or enquiries.</p>
              <p>Accepted human labels: <strong>{intake.reviewed_human_labels}</strong> · Benchmark-ready cases: <strong>{intake.benchmark_ready_cases}</strong> · Automatic Jev evaluation: <strong>Off</strong></p>
              <p>Next: authenticate independent reviewers, inspect original URL/content evidence, document rights, and label each actual case. URL-level cases cannot be compared directly with the separate one-shot aggregate Jev decision.</p>
            </> : <p className={styles.cardDescription}>Private reviewed source cases are not available or failed their pinned receipt checks. No human ground-truth labels have been inferred.</p>}
          </div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="seo-ai-first-pass">
          <div className={styles.sectionLead}><div>
            <span className={styles.overline}>04 / AI DOES THE FIRST PASS</span>
            <h2 id="seo-ai-first-pass">AI original-page investigation</h2>
          </div><span>LOCAL MODEL · SHADOW ONLY</span></div>
          <div className={styles.platformCard}>
            {ai ? <>
              <p className={styles.cardDescription}>Empire's existing local Laya model attempted initial evidence review of {ai.observed_cases_reviewed} original first-party URL observations. This is AI-led triage, not manual data entry, and it incurred zero external Jev usage charges.</p>
              <p>AI proposals: <strong>{ai.model_candidates_returned}</strong> · Deeper AI research required: <strong>{ai.deep_ai_research_queue_count}</strong> · Human labels fabricated: <strong>0</strong></p>
              <p>Unverified historical content still needs source research. The model does not automatically redirect, publish, contact buyers or infer revenue. Human approval is reserved for public or commercially consequential actions.</p>
            </> : <p className={styles.cardDescription}>Local AI first-pass receipt is unavailable or not source verified. The original GSC evidence remains available; no AI result has been invented.</p>}
          </div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="seo-jev-case-assessments">
          <div className={styles.sectionLead}><div>
            <span className={styles.overline}>05 / TYPE SAFE JEV FULL COHORT</span>
            <h2 id="seo-jev-case-assessments">AI-reviewed original-page cases</h2>
          </div><span>MODEL RESULTS · NOT SEO FIXES</span></div>
          <div className={styles.platformCard}>
            {jevCases ? <>
              <p className={styles.cardDescription}><strong>{jevCases.validated_model_responses} actual Jev assessments</strong> across {jevCases.verified_provider_batches} bounded provider calls. No buyer or customer data was sent; first-party URL paths and page-only metrics formed the evidence.</p>
              <p>Source-audit recommendations: <strong>{jevCases.model_choice_counts.SOURCE_AUDIT ?? 0}</strong> · Confidence at least 80%: <strong>{jevCases.model_confidence_at_least_0_80}</strong> · Needs deeper AI research: <strong>{jevCases.model_confidence_below_0_80}</strong></p>
              <p>Total reported inference cost: <strong>${jevCases.reported_cost_usd.toFixed(6)}</strong> · Repeat billing: <strong>Off</strong></p>
              <p>The next AI task is recovering original source and publication-rights evidence. Historical content is not yet verified; no redirects, public changes, buyer outreach or payments were authorised.</p>
            </> : <p className={styles.cardDescription}>Validated Jev provider results for all 30 owned URLs are unavailable. This desk does not invent case assessments.</p>}
          </div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="jev-seo-deployment">
          <div className={styles.sectionLead}><div>
            <span className={styles.overline}>06 / EVIDENCE TO ORGANIC DEPLOYMENT</span>
            <h2 id="jev-seo-deployment">SEO deployment research queue</h2>
          </div><span>NOT PUBLISHED · APPROVAL GATED</span></div>
          <div className={styles.platformCard}>
            {deployment ? <>
              <p className={styles.cardDescription}>Jev's {deployment.jev_predictions_observed} source-audit recommendations are consolidated into <strong>{deployment.core_topic_research_observations} core-topic research cases</strong> and <strong>{deployment.off_core_urls_retained_404} unrelated URLs to leave at 404</strong>. The original GSC sample recorded {deployment.sample_page_impressions} impressions and {deployment.sample_page_clicks} clicks—not verified buyers or revenue.</p>
              <ol className={styles.todoList}>
                {deployment.research_workstreams.map((work, i) => <li key={work.workstream}>
                  <span>{String(i+1).padStart(2,"0")}</span><div>
                    <strong>{work.workstream.replaceAll("_"," ").toLowerCase()}</strong>
                    <small>{work.case_count} URLs · {work.sample_impressions} sampled impressions</small>
                    <p>{work.status === "RESEARCH_ONLY" ? "Research genuine content and related existing pages; original source and rights approval required" : "Keep legacy URLs at 404 pending stronger, relevant demand evidence"}</p>
                  </div>
                </li>)}
              </ol>
              <p>This is a <strong>deployment research shortlist, not a live website release</strong>. No mass redirects, auto-publishing, traffic-lift claims or commercial payouts are enabled.</p>
            </> : <p className={styles.cardDescription}>Deployment research queue is unavailable or its verified receipt failed validation. No website changes have been assumed.</p>}
          </div>
        </section>
        <section className={styles.analyticsSection} aria-labelledby="seo-jev-portfolio">
          <div className={styles.sectionLead}><div>
            <span className={styles.overline}>02 / SEO DEPARTMENT STRATEGY</span>
            <h2 id="seo-jev-portfolio">High-level Jev decisions</h2>
          </div><span>REVIEW ONLY</span></div>
          <div className={styles.platformCard}>
            {department ? <>
              <p className={styles.cardDescription}>{department.task_count} decision tasks across the existing SEO department; {department.aggregate_observed_lane_count} have aggregate evidence to investigate. There are no Jev model scores, verified case labels or authorised automatic actions.</p>
              <details open><summary><strong>Observed evidence to investigate</strong></summary>
                <ol className={styles.todoList}>
                  {department.task_board.filter(x=>x.evidence_state==="AGGREGATE_REVIEW_AVAILABLE").map((task,i)=><li key={task.task_id}>
                    <span>{String(i+1).padStart(2,"0")}</span><div>
                      <strong>{task.title}</strong>
                      <small>{task.existing_owner} · Source aggregates, not Jev scores</small>
                      <p>{task.next_evidence_action.replaceAll("_"," ").toLowerCase()}</p>
                    </div>
                  </li>)}
                </ol>
              </details>
              <details><summary><strong>Held for original evidence</strong> — {department.task_count-department.aggregate_observed_lane_count}</summary>
                <ol className={styles.todoList}>
                  {department.task_board.filter(x=>x.evidence_state==="ORIGINAL_EVIDENCE_REQUIRED").map((task,i)=><li key={task.task_id}>
                    <span>{String(i+1).padStart(2,"0")}</span><div>
                      <strong>{task.title}</strong>
                      <small>{task.existing_owner} · Human evidence review required</small>
                      <p>{task.next_evidence_action.replaceAll("_"," ").toLowerCase()}</p>
                    </div>
                  </li>)}
                </ol>
              </details>
            </> : <p className={styles.cardDescription}>The aggregate SEO department evidence board is unavailable or its safety contract did not verify. No work prioritisation has been inferred.</p>}
          </div>
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
