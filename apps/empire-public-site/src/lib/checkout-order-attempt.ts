/**
 * Preserve a single browser-page order identity over retries of the same
 * commercial terms. The EmpireDB backend binds its order UUID to this key.
 * This state is ephemeral and contains no persisted buyer information.
 */
export type CheckoutOrderInput = {
  product_code: string;
  amount_cents: number;
  business_name: string;
  email: string;
  target_domain: string;
  payer_wallet: string;
  terms_accepted: boolean;
};

export type CheckoutOrderAttempt = {
  fingerprint: string;
  idempotencyKey: string;
};

export function reuseCheckoutOrderAttempt(
  existing: CheckoutOrderAttempt | null,
  details: CheckoutOrderInput,
  newSecureKey: () => string,
): CheckoutOrderAttempt {
  // Include displayed catalogue price so changed terms cannot silently
  // reuse a previously accepted order identity.
  const fingerprint = JSON.stringify([
    details.product_code,
    details.amount_cents,
    details.business_name.trim(),
    details.email.trim().toLowerCase(),
    details.target_domain.trim().toLowerCase(),
    details.payer_wallet.trim(),
    details.terms_accepted,
  ]);
  if (existing?.fingerprint === fingerprint) return existing;
  const idempotencyKey = newSecureKey();
  if (
    typeof idempotencyKey !== "string" ||
    !/^[a-zA-Z0-9-]{8,128}$/.test(idempotencyKey)
  ) {
    throw new Error("secure_checkout_key_unavailable");
  }
  return { fingerprint, idempotencyKey };
}
