/**
 * Privacy-first integration boundary for PostHog and OpenReplay.
 *
 * No SDK import, remote script, cookie, user ID, replay, analytics
 * autocapture, network call or tenant guess occurs by loading this file.
 * Actual SDK injection requires separately approved runtime setup.
 */
export type FlagshipUxEvent =
  | "results_viewed"
  | "evidence_explanation_opened"
  | "next_action_viewed"
  | "first_verified_result_observed"
  | "unsupported_result_reported";

export type CustomerResultState =
  | "UNKNOWN"
  | "OBSERVED_UNVERIFIED"
  | "EVIDENCE_HELD"
  | "VERIFIED"
  | "VERIFIED_ZERO";

export interface ManualPostHogCapture {
  capture: (event: string, properties: Record<string, boolean | string>) => void;
}

export interface ManualOpenReplaySession {
  start: () => void;
}

/** Never accept arbitrary property bags, links, names or buyer details. */
export function captureFlagshipUxEvent(
  provider: ManualPostHogCapture | null,
  event: FlagshipUxEvent,
  evidenceState: CustomerResultState,
  permission: {
    consentGranted: boolean;
    ownerApproved: boolean;
    providerConnected: boolean;
    tenantAuthorityVerified: boolean;
    manualEventsOnly: boolean;
  },
): "LOCAL_ONLY" | "CAPTURED_MANUAL_EVENT" {
  const events: readonly string[] = [
    "results_viewed",
    "evidence_explanation_opened",
    "next_action_viewed",
    "first_verified_result_observed",
    "unsupported_result_reported",
  ];
  const states: readonly string[] = [
    "UNKNOWN", "OBSERVED_UNVERIFIED", "EVIDENCE_HELD",
    "VERIFIED", "VERIFIED_ZERO",
  ];
  if (!events.includes(event) || !states.includes(evidenceState)) {
    throw new Error("Unrecognized product result event or evidence state");
  }
  // Never count a first verified result if the authoritative UI state is
  // unknown, inferred or held. Customer success metrics are not click proxies.
  if (event === "first_verified_result_observed" && evidenceState !== "VERIFIED") {
    return "LOCAL_ONLY";
  }
  if (!provider || !permission.consentGranted || !permission.ownerApproved ||
      !permission.providerConnected || !permission.tenantAuthorityVerified ||
      !permission.manualEventsOnly) {
    return "LOCAL_ONLY";
  }
  // Crucially exclude URL, metadata, product/tenant IDs, PII and event text.
  provider.capture("empire.flagship." + event, {
    evidence_state: evidenceState,
    verified_revenue_inferred: false,
    session_recorded_by_this_event: false,
  });
  return "CAPTURED_MANUAL_EVENT";
}

/** Independently opt-in diagnostic ONLY. Not called by current UI. */
export function startFlagshipReplayForApprovedDiagnostic(
  provider: ManualOpenReplaySession | null,
  permission: {
    explicitSessionConsent: boolean;
    authenticatedTenant: boolean;
    ownerApproved: boolean;
    privacyRedactionValidated: boolean;
    agplAndEnterpriseLicenseReviewed: boolean;
    retentionAndDeletionApproved: boolean;
    noPaymentOrContactCapture: boolean;
  },
): "REPLAY_DISABLED" | "CONSENTED_DIAGNOSTIC_STARTED" {
  if (!provider ||
      !permission.explicitSessionConsent ||
      !permission.authenticatedTenant ||
      !permission.ownerApproved ||
      !permission.privacyRedactionValidated ||
      !permission.agplAndEnterpriseLicenseReviewed ||
      !permission.retentionAndDeletionApproved ||
      !permission.noPaymentOrContactCapture) {
    return "REPLAY_DISABLED";
  }
  provider.start();
  return "CONSENTED_DIAGNOSTIC_STARTED";
}
