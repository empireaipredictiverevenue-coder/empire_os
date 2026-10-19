# Original forecast registry bridge

19 October 2026 | Predictive Intelligence branch

Continue from commit 933582a3. This feature extends the existing calibration audit. It does not create a separate prediction registry or economic model.

The bridge accepts a bounded list of known original forecast references and uses the existing single-reference readback interface. It is disabled by default and requires an explicit read-only caller decision.

It validates the scoped response identity, original checksum, issue date, registration date and outcome chronology before producing aggregate status counts.
