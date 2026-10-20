/**
 * Founder-approved orbital-A ring artwork, separated from the low-resolution
 * reference wordmark so our own accessible typography remains crisp at every
 * viewport. The mark is an unchanged pixel crop of the authorised reference.
 */
export default function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`approved-brand${compact ? " approved-brand-compact" : ""}`}
      role="img"
      aria-label="Empire AI — Predictive Revenue Infrastructure"
    >
      <img
        className="approved-brand-mark"
        src="/brand/empire-orbital-a-reference-mark.webp"
        width="86"
        height="60"
        alt=""
        decoding="async"
      />
      <span className="approved-brand-type" aria-hidden="true">
        <strong>EMPIRE AI</strong>
        <small>PREDICTIVE REVENUE INFRASTRUCTURE</small>
      </span>
    </span>
  );
}
