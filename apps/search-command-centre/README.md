# Empire Search Command Centre

Phase 5 frontend for governed Search Intelligence.

## Authority

- Read-only/recommendation surface.
- No content publishing.
- No sitemap or index submission.
- No redirect, robots or canonical mutation.
- No production credentials in the browser.

The app reads the EmpireOS `/v1/search/*` contract from the server-only `EMPIRE_SEARCH_API_BASE_URL` environment variable. If the API or canonical repository is unavailable, the UI shows a gated/unknown state instead of fabricated zero metrics.

## Local validation

```bash
npm run lint
npm run build
```

Copy `.env.example` to a local ignored env file only when an approved Search API endpoint is available.
