/** Safe retry identity for the existing first-party enterprise deployment form.
 * No browser storage, visitor tracking, network traffic or customer-data sink.
 * Different request or permission details must never reuse an old ingest key.
 */
export type PredictiveInterestDetails = Readonly<{
  product_code: string;
  business_name: string;
  email: string;
  domain: string;
  industry: string;
  geography: string;
  annual_revenue_band: string;
  desired_outcome: string;
  systems: readonly string[];
  contact_consent: boolean;
  website: string;
}>;

export type PredictiveInterestAttempt = Readonly<{
  fingerprint: string;
  idempotencyKey: string;
}>;

export function reusePredictiveInterestAttempt(
  existing: PredictiveInterestAttempt | null,
  details: PredictiveInterestDetails,
  generateSecureKey: () => string,
): PredictiveInterestAttempt {
  // Fingerprint never leaves the browser component; it is not analytics or
  // an actual source/customer identity.
  const fingerprint = JSON.stringify([
    details.product_code,
    details.business_name.trim(),
    details.email.trim().toLowerCase(),
    details.domain.trim().toLowerCase(),
    details.industry.trim(),
    details.geography.trim(),
    details.annual_revenue_band,
    details.desired_outcome.trim(),
    [...details.systems].sort(),
    details.contact_consent,
    details.website,
  ]);
  if (existing?.fingerprint === fingerprint) return existing;
  const idempotencyKey = generateSecureKey();
  if (typeof idempotencyKey !== "string" ||
      !/^[a-zA-Z0-9][a-zA-Z0-9_:.-]{7,127}$/.test(idempotencyKey)) {
    throw new Error("secure_predictive_key_unavailable");
  }
  return { fingerprint, idempotencyKey };
}
