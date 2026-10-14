/** Server-side only; read the existing Founder API with no client secrets. */
export type FounderJevStatus = {
  schema_version: "empire.founder_jev_status.v1";
  mode: "OBSERVE";
  decision_contract_version: string;
  native_model_primitives: string[];
  native_compatibility_tested: boolean;
  commercial_model_calibrated: boolean;
  shared_vane_openmanus_research_core_integrated?: boolean;
  jev_evidence_gap_plan_available?: boolean;
  jev_public_research_execution_activated?: boolean;
  jev_research_source_validation_completed_live?: boolean;
  jev_official_primary_continuity_implemented?: boolean;
  jev_official_primary_continuity_production_enabled?: boolean;
  jev_research_spend_gbp?: number;
  economic_reader_configured: boolean;
  crm_reader_configured?: boolean;
  crm_prospect_review_available?: boolean;
  reply_candidate_reader_prepared?: boolean;
  reply_candidate_migration_051_applied?: boolean | null;
  verified_original_reply_count?: number | null;
  owned_imap_header_review_configured?: boolean;
  owned_imap_header_review_only?: boolean;
  mailbox_crm_alignment_verified?: boolean;
  signed_first_party_ingress_verifier_implemented?: boolean;
  signed_first_party_ingress_producer_configured?: boolean;
  signed_first_party_ingress_producer_independently_audited?: boolean;
  independently_verified_buyer_replies?: number | null;
  mail_ingress_source_truth_probe_implemented?: boolean;
  mail_ingress_source_truth_checked_by_api?: boolean;
  first_party_reply_ingress_production_verified?: boolean;
  sovereign_ingress_receipt_pipeline_tested?: boolean;
  sovereign_ingress_mta_deployed?: boolean;
  sovereign_ingress_signer_production_audited?: boolean;
  independent_founder_authorizer_configured: boolean;
  real_canonical_rows_verified: number | null;
  buyers_identified: number | null;
  verified_revenue: number | null;
  founder_review_only: boolean;
  send_authorized: boolean;
  live_commercial_routing: boolean;
  production_activated: boolean;
  execution_authority: "none";
};

export type FounderJevRead = {
  available: boolean;
  data: FounderJevStatus | null;
  reason: string | null;
};

export async function getFounderJevStatus(): Promise<FounderJevRead> {
  const base =
    process.env.EMPIRE_API_BASE_URL?.trim() ??
    process.env.EMPIRE_SEARCH_API_BASE_URL?.trim();

  if (!base) {
    return { available: false, data: null, reason: "Founder API not configured" };
  }

  try {
    const response = await fetch(
      base.replace(/\/$/, "") + "/v1/founder-jev/status",
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(5000),
      },
    );
    if (!response.ok) {
      return { available: false, data: null, reason: "JEV API unavailable" };
    }

    const body: unknown = await response.json();
    if (!body || typeof body !== "object") {
      return { available: false, data: null, reason: "Invalid API response" };
    }
    const packet = body as Record<string, unknown>;
    if (
      packet.schema_version !== "empire.founder_jev_status.v1" ||
      packet.mode !== "OBSERVE" ||
      packet.execution_authority !== "none" ||
      !Array.isArray(packet.native_model_primitives) ||
      typeof packet.native_compatibility_tested !== "boolean" ||
      typeof packet.commercial_model_calibrated !== "boolean" ||
      typeof packet.economic_reader_configured !== "boolean" ||
      typeof packet.independent_founder_authorizer_configured !== "boolean" ||
      typeof packet.production_activated !== "boolean" ||
      typeof packet.live_commercial_routing !== "boolean"
    ) {
      return { available: false, data: null, reason: "JEV evidence contract invalid" };
    }

    return { available: true, data: body as FounderJevStatus, reason: null };
  } catch {
    return { available: false, data: null, reason: "JEV API unreachable" };
  }
}
