# Empire OS Inbound Email — Brevo path (PROVEN 2026-08-30)

REPLACES Cloudflare Email Routing -> Gmail (Gmail silently dropped CF forwards, zero bounces).

## Live path
buyer replies -> founder@empire-ai.co.uk (MX inbound1/2.sendinblue.com)
  OR buy@reply.empire-ai.co.uk
  -> Brevo inbound parse
  -> webhook inboundEmailProcessed
  -> https://track.empire-ai.co.uk/v1/inbound/brevo (alias /v1/inbound/brevo-apex)
  -> container hub (empire-hub, empire-hub-8081.service)
  -> si_inbox + email_replies (status=matched)

## Brevo setup (done)
- domains: empire-ai.co.uk + reply.empire-ai.co.uk, both authenticated
  PUT /v3/senders/domains/{name}/authenticate
- webhooks: id 2160019 (reply.empire-ai.co.uk), id 2160027 (apex)
- DNS: apex MX flipped from route1/2/3.mx.cloudflare.net to inbound1/2.sendinblue.com
  reply.empire-ai.co.uk: MX inbound1/2 + TXT brevo-inbound-verification

## Pitfalls (hard-won)
1. Webhook URL must have NO query string. ?src=apex registered but SILENTLY NEVER FIRED.
2. Webhook must exist BEFORE the email arrives — events before creation are lost, no replay.
3. Hub boot takes ~90s before :8081 binds. Don't test earlier.
4. /v1/inbound/parse expects {from_email,subject,body}; Brevo shape goes to /v1/inbound/brevo.
5. Blast reply_to = founder@empire-ai.co.uk (mail_sender.py line ~140, deployed host+container). Proven: real external reply to founder@ -> Brevo apex MX -> webhook 2160027 -> si_inbox row 8 status=matched.
   Push mail_sender.py + hub.py into empire-hub after host edits; restart both sides.

## Verification (last run)
si_inbox id 8: flavag83@gmail.com -> founder@empire-ai.co.uk, matched, 2026-08-30 18:04:42
email_replies id 9 linked inbox_id=8.

## Fallback
Gmail IMAP poller (empire-inbound-reply, imap_defensive_wrapper.py) = backup only now.
empire.co.uk = separate zone, LIVE Fastmail MX — never delete.

## AUTO-RESPONDER (live 2026-08-30, proven end-to-end)
- empire_os/auto_responder.py, triggered from inbound_replies.insert_inbound (never breaks capture)
- Classifies BUY/INFO/UNSUB -> BUY: auto_onboard (tenant+seat) -> pay-link (real vault 0x1339...) -> email back
- Send path: GMAIL RELAY smtp.gmail.com:465, login empireaipredictiverevenue@gmail.com,
  pw /root/empire_secrets/gmail_app_password_predictive (600, host+container). Reply-To founder@empire-ai.co.uk.
  Brevo->Gmail SILENTLY DROPS; Gmail relay->Gmail lands INBOX. Non-Gmail buyers also fine via relay.
- UNSUB: flags si_outbox recipient, no reply. Dedup: auto_reply_log per inbox_id.
- PROOF: si_inbox row 277 -> arlog 75 BUY pay_link_reply ok:true -> "Re: yes send me the pay link AR-6"
  with bsc: pay link in recipient INBOX (msg 3005).
- WARNING: old IMAP pollers (empire-inbound-reply*) were stopped+disabled host+container 08-30.
  They flooded si_inbox (194 junk rows, purged) and burned Brevo daily quota. NEVER re-enable.

## 2026-08-30 EVENING: HTML replies + catalogue + dedup verified
- email_templates.py: branded HTML (dark #0a1628, cyan #00BCD4, blue #2196F3,
  neon #00FF88), 600px table layout, inline styles. blast/paylink/info x
  (html+text). Real vault only.
- auto_responder: multipart/alternative via _reply_to_buyer(html=). Subjects:
  "Your Empire AI buyer seat, activation link inside" etc. No em-dashes.
- hub enqueue: html_body column carried (INSERT patched host+container).
- run_buyer_blast.py: rewritten. Subject "Roofing leads in Orlando, FL, $4 per
  qualified lead" (quiet, specific, no brand name). One ask: reply "sample".
  No raw vault, no price wall. Catalogue mention + link only.
- VERIFIED end-to-end 3x: external reply -> si_inbox matched -> BUY classify
  -> onboard -> HTML pay-link reply -> Gmail INBOX msg 3006 (brand colors +
  real vault + Reply-To founder@).
- Dedup VERIFIED: same sender <7d -> skipped (already_replied_7d).
- Gmail quirk: self-addressed (predictive->predictive) HTML replies can be
  delayed/merged. Plain+HTML to OTHER gmail (flavag83) land INBOX instantly.
  Real buyers = other domains = fine.
- Test artifacts purged (inbox>=276, arlog, test tenant/sub). FK order:
  auto_reply_log + email_replies reference si_inbox; delete children first.
