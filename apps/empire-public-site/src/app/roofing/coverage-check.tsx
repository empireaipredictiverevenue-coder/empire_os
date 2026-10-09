"use client";

import { useState, type FormEvent } from "react";

type CoverageResponse = {
  schema_version: string;
  status: string;
  coverage_guidance: string;
  source_expires_at: string;
  call_authorized: boolean;
  execution_authority: string;
  buyer_route_verified: boolean;
};

type CheckResult =
  | { kind: "idle" }
  | { kind: "invalid" }
  | { kind: "unavailable" }
  | { kind: "covered"; zip: string }
  | { kind: "not-listed"; zip: string };

function validPreview(value: unknown): value is CoverageResponse {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<CoverageResponse>;
  if (
    item.schema_version !== "empire.lead_smart.zip_check_response.v1" ||
    item.status !== "GUIDANCE_ONLY" ||
    item.call_authorized !== false ||
    item.execution_authority !== "NONE" ||
    item.buyer_route_verified !== false ||
    !["LISTED_IN_RECENT_COVERAGE", "NOT_LISTED_IN_RECENT_COVERAGE"].includes(item.coverage_guidance ?? "") ||
    typeof item.source_expires_at !== "string"
  ) return false;
  const expiry = Date.parse(item.source_expires_at);
  return Number.isFinite(expiry) && expiry > Date.now() && expiry <= Date.now() + 60 * 60 * 1000;
}

export default function RoofingCoverageCheck() {
  const [zip, setZip] = useState("");
  const [result, setResult] = useState<CheckResult>({ kind: "idle" });
  const [busy, setBusy] = useState(false);

  async function checkZip(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submitted = zip.trim();
    if (!/^[0-9]{5}$/.test(submitted)) {
      setResult({ kind: "invalid" });
      return;
    }
    setBusy(true);
    try {
      const response = await fetch("/roofing/coverage-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ zip: submitted }),
        cache: "no-store",
      });
      if (!response.ok) throw new Error("coverage unavailable");
      const data: unknown = await response.json();
      if (!validPreview(data)) throw new Error("unverified or expired coverage");
      setResult(
        data.coverage_guidance === "LISTED_IN_RECENT_COVERAGE"
          ? { kind: "covered", zip: submitted }
          : { kind: "not-listed", zip: submitted }
      );
    } catch {
      setResult({ kind: "unavailable" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="roofing-zip-check-heading" className="border-b border-[#cfe1f6] bg-[#edf7ff]">
      <div className="mx-auto grid max-w-[1260px] gap-6 px-5 py-10 sm:px-8 md:grid-cols-[1fr_1.2fr] md:items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#0769d7]">Homeowner ZIP check</p>
          <h2 id="roofing-zip-check-heading" className="mt-3 text-2xl font-extrabold tracking-tight text-[#081b3a] sm:text-3xl">
            Check recent roofing coverage guidance
          </h2>
          <p className="mt-3 text-sm leading-6 text-[#405b7e]">
            Enter the five-digit US ZIP code of the property. This is a planning preview only;
            a listed ZIP does not guarantee a contractor, available buyer, or payable call.
          </p>
          <p className="mt-3 text-xs leading-5 text-[#405b7e]">
            Buyer-reported operating hours: Monday–Friday 8 AM–6 PM, weekends 10 AM–4 PM Central Time.
            Availability and seasonal time interpretation remain subject to confirmation.
          </p>
        </div>
        <div className="rounded-2xl border border-[#c7def3] bg-white p-5 shadow-[0_12px_35px_rgba(5,58,113,.08)] sm:p-6">
          <form onSubmit={checkZip} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex-1 text-sm font-semibold text-[#14355b]">
              Property ZIP code
              <input
                name="zip"
                inputMode="numeric"
                autoComplete="postal-code"
                maxLength={5}
                value={zip}
                onChange={(event) => { setZip(event.target.value); setResult({ kind: "idle" }); }}
                placeholder="e.g. 00501"
                aria-describedby="roofing-zip-result"
                className="mt-2 min-h-12 w-full rounded-xl border border-[#aacbeb] bg-[#fafdff] px-4 text-base font-medium text-[#112b4a] outline-none focus:ring-2 focus:ring-[#087af5]"
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="min-h-12 rounded-xl bg-[#075ec6] px-5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
            >
              {busy ? "Checking..." : "Check ZIP"}
            </button>
          </form>
          <div id="roofing-zip-result" aria-live="polite" className="mt-4 min-h-12 text-sm leading-6 text-[#284b73]">
            {result.kind === "invalid" && "Enter a valid five-digit US ZIP code."}
            {result.kind === "unavailable" && "Coverage guidance is temporarily unavailable or expired. No call route is enabled."}
            {result.kind === "covered" &&
              `ZIP ${result.zip} appeared in a recent coverage snapshot. This does not confirm live service or call eligibility.`}
            {result.kind === "not-listed" &&
              `ZIP ${result.zip} was not listed in the current guidance snapshot. No call route is enabled.`}
            {result.kind === "idle" && "No phone number will be enabled by this preview."}
          </div>
          <p className="mt-3 text-xs text-[#547092]">Your property ZIP is sent to Empire AI for an immediate read-only coverage check. This form does not request your name, telephone number, or contact details.</p>
        </div>
      </div>
    </section>
  );
}
