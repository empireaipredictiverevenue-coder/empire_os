# Feature Specification: Free Audit Lead Magnet

**Feature Branch**: `001-free-audit-lead-magnet`
**Created**: 2026-07-21
**Status**: Draft
**Input**: Build free SEO audit endpoint + landing page that captures email+niche+metro, runs claude-seo checks, returns score + PDF, feeds Empire funnel.

## User Scenarios & Testing

1. **Visitor lands on /tools/audit/** → enters URL + email → gets instant score (A-F) + "Full report emailed"
2. **Email arrives** → PDF with CWV, on-page, tech checks, 3 quick wins → CTA: "$10 trial for full fix"
3. **Empire funnel** → lead auto-enters `si_buyer_outreach` with niche/metro → `funnel_agent` tracks discovered→matched
4. **Cortex** → audit volume + conversion rate feeds predictive revenue

## Functional Requirements

- **FR-001**: POST `/v1/audit/free` accepts `{url, email, niche?, metro?}` returns `{score, grade, checks, pdf_url}`
- **FR-002**: Runs `fetch_page` + `parse_html` + `pagespeed_check` (if key) + quick tech checks
- **FR-003**: Score 0-100, grade A-F, 3 prioritized fixes
- **FR-004**: Generates branded PDF via WeasyPrint/Jinja2
- **FR-005**: Emails PDF via Resend (onboarding@resend.dev for testing)
- **FR-006**: Stores lead in `si_buyer_outreach` with `source=free_audit`, `niche`, `metro`
- **FR-007**: Landing page at `/tools/audit/` (cinematic_lp_agent render)
- **FR-008**: Rate limit: 5 req/min/IP, 20 req/day/email

## Non-Functional

- **NFR-001**: Response < 10s (async PDF generation)
- **NFR-002**: No API key required for free tier (PSI optional)
- **NFR-003**: GDPR/CCPA compliant (explicit consent checkbox)
- **NFR-004**: Deploy to empire-hub (port 8081) or new audit-api container

## Integration Points

- `empire_os.audit_api` (new module)
- `empire_os.hub` → add `/v1/audit/free` endpoint
- `empire_os.agents.cinematic_lp_agent` → render landing page
- `empire_os.mail_sender` → send PDF
- `empire_os.funnel` → auto-advance lead
- `empire_os.cortex_engine` → track audit KPIs