# Empire AI — current flagship brokerage first-paint restoration

Date: 21 October 2026. Founder continued the approved brokerage visibility correction after the newer V2 flagship website had unintentionally pushed premium services far below the initial viewport.

## Measured current regression

- Public `GET https://empire-ai.co.uk/commercial`: HTTP 200, exact SHA256 `c0f8518d0113ea30faf38cd4f2f769e80fd2ff46d715e4d86100cde6f4659b7f` matching current `/srv/empire_os/apps/empire-public-site/out/commercial.html`.
- The initial HTML lacks both service names, while a JavaScript-hydrated Edge browser renders the services at 1,997 px desktop / 3,470 px mobile below the fold, no observed exceptions.
- Two live GET premium options remain unpriced/nonbinding; payment and outreach remain disabled.

## Exact scoped candidate

Isolated worktree: `/home/ubuntu/empire_worktrees/brokerage_current_flagship_first_paint_fix_20261021`.

Two component/page source changes only: move `BrokeragePremiumDiscovery` just below current Commercial hero, retain pricing and enquiry form, and render an unpriced informational premium preview in initial HTML before live GET hydration. The unchanged real form is available only after a verified GET. This is the previously founder-approved first-paint design adapted to the **current** revised flagship source.

- `next build --webpack` and TypeScript: successful, 19 static routes generated.
- Old current HTML: 112 visible text segments; new current HTML: 122, with all 112 original text segments preserved in order.
- Both premium service names present once in generated initial HTML before existing `Founder-approved starting prices`.
- Old HTML SHA256 `c0f8518d0113ea30faf38cd4f2f769e80fd2ff46d715e4d86100cde6f4659b7f`; new generated HTML SHA256 `404d87e3c3ee366415662389992c0001eb25e0bcf24e526ef898b1f0e5f2e03e`.
- Static delta: 13 new hashed assets, 315,856 bytes; 28 matching existing assets; **zero existing-name collisions**.
- Five release and rollback sandbox tests passed; five frontend catalogue safety tests passed.

## Exact guarded release interface

```bash
cd /home/ubuntu/empire_worktrees/brokerage_current_flagship_first_paint_fix_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.release_brokerage_current_first_paint_20261021 --preflight

# Only for approved exact-baseline website publication after preflight:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.release_brokerage_current_first_paint_20261021 \
  --apply-founder-approved-first-paint

# After publication:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.release_brokerage_current_first_paint_20261021 --verify-live
```

The release script atomically publishes only the current `/commercial` HTML and **new-only** Next static assets; saves private rollback copy mode 0600; never overwrites existing shared assets, restarts services, changes another site page, creates a buyer, changes CRM, sends email or enables financial gates. Concurrent site changes fail closed. The canonical source checkout remains another agent's dirty branch; this isolated commit must be reconciled in the website owner release process to avoid a future regression.
