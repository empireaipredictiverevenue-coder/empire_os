/**
 * Founder-approved blue-halo orbital-A identity (27 Oct brand board).
 * Stored 820x160 PNG is SHA256 pinned; no re-generated logo substitute.
 * No original native vector master has been verified.
 */
export default function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`approved-brand${compact ? " approved-brand-compact" : ""}`}
      role="img"
      aria-label="Empire AI — Predictive Revenue Infrastructure"
    >
      <img
        className="approved-brand-reference"
        src="/brand/empire-ai-primary-orbital-a-founder-approved.png"
        width="820"
        height="160"
        alt=""
        decoding="async"
      />
    </span>
  );
}
