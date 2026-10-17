/**
 * Preserve one commercial enquiry identity across safe retries in the same
 * browser tab, so an uncertain network response cannot mint a second ingest
 * key for the identical visitor-consented request. Nothing is persisted.
 */
export type CommercialInterestDetails = {
  product_code: string;
  business_name: string;
  email: string;
  domain: string;
  industry: string;
  geography: string;
  desired_outcome: string;
  contact_consent: boolean;
  website: string;
};

export type CommercialInterestAttempt = Readonly<{
  fingerprint: string;
  idempotencyKey: string;
}>;

export function reuseCommercialInterestAttempt(
  existing: CommercialInterestAttempt | null,
  details: CommercialInterestDetails,
  newSecureKey: () => string,
): CommercialInterestAttempt {
  // Materially changed product/contact/request details require a fresh key.
  // This fingerprint lives only inside the mounted component, never in storage
  // or analytics. It is not a provider/customer identifier.
  const fingerprint = JSON.stringify([
    details.product_code,
    details.business_name.trim(),
    details.email.trim().toLowerCase(),
    details.domain.trim().toLowerCase(),
    details.industry.trim(),
    details.geography.trim(),
    details.desired_outcome.trim(),
    details.contact_consent,
    details.website,
  ]);
  if (existing?.fingerprint === fingerprint) return existing;
  const idempotencyKey = newSecureKey();
  // Existing EmpireOS first-party interest service validates ASCII key format.
  if (typeof idempotencyKey !== "string" ||
    !/^[a-zA-Z0-9][a-zA-Z0-9_:.-]{7,127}$/.test(idempotencyKey)) {
    throw new Error("secure_commercial_key_unavailable");
  }
  return {fingerprint,idempotencyKey};
}
