# Empire PPL — Texas Flood Ad Copy

Raw, urgent, neighbor-tone. No testimonials. No "trusted since 2003."
Each variant is a separate ad group; spin them, don't mix.

All variants must surface a working 5-digit zip intake form URL and
honor PPL_DISASTER_MODE (the ad never runs if disaster mode is on
and the niche is in the block-list — that's enforced via the api).

---

## Variant A — Active Leak

```
Got water coming in and not stopping.

Not "a little wet." Water on the floor, water on the rug, water where
it shouldn't be. In a flash flood area the line between "got this" and
"need a truck" is about 12 hours. Be honest with yourself.

Enter your zip. We ring the closest local water-removal crew in
under 15 minutes. Pumps on the truck. Insurance paperwork handled.

[Enter ZIP] → Call dispatch

No call centers. No 60-minute holds. Your county, your crew.
```

---

## Variant B — Ceiling Bulge / Collapse

```
Your ceiling's sagging. Don't wait for it.

After a flood, drywall holds water like a sponge. It gets heavy.
Then it falls. Usually on the kid's room. Usually at 3am.

Don't poke it. Don't put a bucket under it and pretend.

Enter your zip. A local crew comes out, cuts the bulge out,
dries the cavity, treats for mold. Insurance doc-photos on the
spot for your claim.

[Enter ZIP] → Call dispatch

Sabinal, Uvalde, Kerrville — answered by a person in your county.
```

---

## Variant C — Wet Carpet & Smell

```
Wet carpet now. Mold tomorrow. Pick one.

You can come back next week and pay $4,800 to rip out subfloor
and redo the bedroom. Or you can have a crew come out today,
pull the carpet, dry the pad (or trash it), and stop the smell
before it starts. Same crew usually handles the doc-photos for
your insurance claim the same visit.

[Enter ZIP] → Call dispatch

Pay-Per-Lead. We don't take commission from the crew; you don't
get upsold on services you didn't ask for.
```

---

## Negative keywords (suggested for ad network)

- "DIY"
- "class action lawsuit"
- "FEMA"
- "red cross"
- "charity"
- "free"
- "lawyer"
- "attorney"
- "insurance company phone number"

(Filters out non-buyer clicks; we don't want to route look-alikes
to "free help" searchers who won't convert to a paid dispatch.)

---

## Compliance notes (operator's responsibility, NOT in code)

- TCPA prior express written consent required before any autodial.
  The zip form is opt-in by submission; phone follow-up must
  be manual or with explicit voice consent captured on call.
- Texas DTPA prohibits certain "disaster pricing" claims — do not
  imply we're affiliated with FEMA, Red Cross, county government.
- "Pay-Per-Lead" disclosure is on the landing page footer (see
  ppl_service.py render_landing_page() fine print).
- TCPA quiet hours: 9pm–8am local time should restrict auto-call;
  the dispatcher loop in ppl_service.py only POSTs JSON, so the
  recipient system must enforce quiet hours itself.

---

## Operator actions before flipping the campaigns live

1. Set real values in /root/empire_os/.env:
   - PPL_DISPATCH_WEBHOOK_URL — where the lead POSTs to
   - PPL_DISPATCH_TEL — number shown to the homeowner
   - PPL_DISPATCH_NAME — name shown on the call button
2. Verify the dispatch team is *actually* on call 24/7 in the
   zip prefixes you've listed. PPL_ALLOWED_ZIPS rejects everything
   else at intake.
3. Have a lawyer say yes. This is not legal advice.
