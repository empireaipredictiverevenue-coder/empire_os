type Source = {
  source: string;
  evidence_ref: string;
  snapshot_digest: string | null;
  snapshot_generated_at: string | null;
  state: string;
};
const states = new Set(["OBSERVED", "NO_SOURCE", "UNAVAILABLE", "HOLD", "UNKNOWN", "STALE"]);
const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function SnapshotEvidence({ payload }: { payload: unknown }) {
  const raw = record(payload) ? payload.intelligence_snapshot_evidence : undefined;
  const valid = record(raw)
    && raw.schema_version === "empire.predictive_revenue.snapshot_evidence.v1"
    && raw.scope === "SYSTEM_AGGREGATE_METADATA_ONLY"
    && raw.execution_authority === "none";
  const rows: Source[] = [];
  if (valid && Array.isArray(raw.sources)) {
    for (const item of raw.sources.slice(0, 3)) {
      if (!record(item) || typeof item.source !== "string"
          || typeof item.evidence_ref !== "string" || typeof item.state !== "string"
          || !states.has(item.state)) continue;
      rows.push({ source: item.source, evidence_ref: item.evidence_ref, state: item.state,
        snapshot_digest: typeof item.snapshot_digest === "string" ? item.snapshot_digest : null,
        snapshot_generated_at: typeof item.snapshot_generated_at === "string" ? item.snapshot_generated_at : null });
    }
  }
  return <section className="panel mt-5" aria-labelledby="snapshot-evidence-title">
    <p className="eyebrow">Original intelligence sources</p>
    <h2 id="snapshot-evidence-title" className="mt-1 text-2xl font-semibold text-white">Cloud · Predictive intelligence · Jev</h2>
    <p className="mt-3 text-sm text-slate-400">Operational snapshot evidence. Snapshot age is not source ingestion lag; a digest does not verify source rights or financial outcomes.</p>
    {rows.length === 3 ? <div className="mt-5 grid gap-4 lg:grid-cols-3">{rows.map((row, i) =>
      <article key={row.source + i} className="min-w-0 rounded-2xl border border-white/10 p-4">
        <h3 className="font-semibold text-white">{row.source}</h3>
        <p className="mt-2 text-sm text-amber-200">{row.state}</p>
        <dl className="mt-3 space-y-2 break-all text-xs text-slate-400">
          <div><dt>Snapshot generated</dt><dd>{row.snapshot_generated_at ?? "UNKNOWN"}</dd></div>
          <div><dt>Evidence reference</dt><dd>{row.evidence_ref}</dd></div>
          <div><dt>SHA-256</dt><dd>{row.snapshot_digest ?? "UNKNOWN"}</dd></div>
        </dl>
      </article>)}</div> : <p role="status" className="mt-4 text-amber-200">UNKNOWN — snapshot evidence contract unavailable or invalid.</p>}
    <p className="mt-4 text-sm text-amber-100">30 / 60 / 90-day forecasts: HOLD — tenant-scoped issued forecasts are not connected to this read model.</p>
    <p className="mt-2 text-xs text-slate-400">This panel contains system metadata only. It does not establish tenant access, prediction accuracy, or verified cash.</p>
  </section>;
}
