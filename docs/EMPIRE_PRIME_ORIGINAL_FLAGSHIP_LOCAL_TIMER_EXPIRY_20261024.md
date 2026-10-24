# Empire AI / Original PRIME — Working Offline Local Timer Expiry

Date: 24 October 2026
Location: isolated original `feature/prime-universal-evidence-fusion-20261024` worktree.
Scope: existing Voice Lab → PRIME → original capability review → **in-process timer sandbox**.
Status: research engineering milestone, no production deployment, no persistent scheduler, no real notification delivery.

## Original architecture and reuse

The original repo has a Scheduling Agent at `empire_os/agents/scheduling_agent.py` for **lead appointment slot proposals**, not household voice timers. The original `empire_os/alerting.py` has live external email/webhook/gateway transports and is NOT safe as a synthetic timer sink. Those original components were neither modified nor invoked. Original ASTRA and original EmpireDB own any future real scheduling/notification activation.

The code extends the existing `empire_os.voice_lab.SherpaKokoroTTS` and `SherpaWhisperSTT` interface and the already-built `classify_synthetic_spoken_timer()` from `prime_flagship_voice_task_rehearsal.py`. It calls the existing `agi_capabilities.review_capability_request()` with no grants to ensure the current unregistered real-timer service cannot be promoted to permitted production authority.

## Code added

1. `empire_os/prime_flagship_local_timer_pilot.py`: strict test-only `InMemoryTimerPilot`. A synthetic request creates a real monotonic in-memory deadline. An explicitly invoked synchronous `poll_due()` checks the deadline, sends at most one expiration event to the injected **`InMemorySink`** and returns a local-only receipt. Locking and pre-dispatch marking protect against concurrent duplicate sends, with terminal failure and **no hidden retry** if the sink fails. A replayed key can never create a second job. Synthetic cancel before dispatch is idempotent; canceled jobs cannot expire. At most 12 keys/session, 1–3600 second budget. Never schedules a systemd unit, queue, cron, external timer, browser notification, phone call, Telegram, Gmail or email.
2. `rehearse_voice_to_local_timer()`: original Voice Lab STT interface → strict PRIME timer-intent classification → explicit original AGI action-HOLD review → original Voice Lab TTS acknowledgement validation → in-memory timer creation. Spoken response explicitly discloses sandbox-only nature and no real-device notification. If STT/intent/TTS fails, a timer is not created. Source audio is a fictitious test prompt; no original real-customer transcript is stored.
3. `scripts/rehearse_prime_actual_local_timer_expiry_20261024.py`: one-shot, no-customer-data original Kokoro synthetic spoken request **"Set a timer for two seconds."**, original Whisper transcription, generated in-memory spoken acknowledgement, real 2-second monotonic deadline, manual poll/expiry and local event readback. Run with finite OS timeout and low CPU priority.
4. `tests/test_prime_flagship_local_timer_pilot.py`: deterministic/virtual-clock tests for due vs not-yet-due, exactly-one receipt, re-poll idempotency, canceled jobs, explicit synthetic-only gate, key/duration validation, monotonic clock rollback, concurrency, sink exception, missing consent/unsafe speech, speech failure, replay and GET-only Founder isolation. There is NO new Founder write endpoint or fake live 'timer scheduled' badge.

## Real offline Voice Lab → Timer → Local sink test

Executed in the isolated original branch with installed local Kokoro/Whisper model assets:

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
timeout 75s nice -n 15 env PYTHONPATH=. \
  /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_prime_actual_local_timer_expiry_20261024.py
```

The real local test returned **exit code 0** and this bounded technical evidence:
- Program elapsed **18.105 s** (includes both actual local speech passes and 2.1-second local expiry wait).
- Generated fictional input audio **57,410 bytes** of original local PCM16.
- Original Whisper classified request duration **2 seconds**.
- Original Kokoro generated sandbox spoken acknowledgement **174,480 bytes**.
- The timer was **not yet due** on the immediate first poll.
- After a real **2.1-second** monotonic wait, exactly **one** local in-process expiration sink event was acknowledged.
- A second poll yielded **no second event**; replay suppression verified.
- Original output status `REAL_LOCAL_SYNTHETIC_TIMER_EXPIRED_ONCE`.
- Voice pipeline status `IN_MEMORY_TIMER_STARTED_NOT_REAL_DELIVERY`.
- External recipient delivery false; no actual user notification, persistent original scheduler, original EmpireDB writes, real microphone, real customer, app-store push, actual phone, email, payment or live commercial operation.

**This is a real local task expiration**, not merely a scripted "timer scheduled" sentence. The sink acknowledgement is only **in-process**, not independently authenticated source-provider proof or delivery to a person's device. The pilot is deliberately polling-based, not a persistent always-on timer; it will not survive process exit, interruption or server restart.

## Release block and what comes next

1. **Original ASTRA/Timers owner**: review the test-only in-memory deadline and implement a durable authenticated scheduler using the original EmpireDB authority, with crash recovery, clock/timezone specifications for reminders, cancellation, idempotent delivery attempt receipts and retries governed by proper source receipts. No second database or unowned cron.
2. **Original Identity/Security/Privacy owner**: require explicit consent for microphone, proof of intended local device/user, cancellation, abuse limits, retention, right to erase, data rights and original per-tenant isolation before real activity.
3. **Original Voice owner**: run multi-trial latency and ASR/TTS accuracy with genuine consented input only after approval, including spoken cancel, noise/accents and interrupted speech.
4. **Original Notification owner**: attach an authentic allowed alert channel, verify **actual receipt at the intended device**, support redelivery and distinguish accepted job from delivered notification. Never use lead-outreach sender or old alerting as implicit permission for personal reminders.
5. **Original Model owner**: independently recover bounded llama.cpp generation for general assistant dialogue. This 2-second timer demonstration required no general-purpose LLM or external service; its previous live generation timeout is still unresolved.
6. **Original Founder/Security owner**: review private cockpit, owner attestation and mobile performance. The Founder read model remains `NOT_RUN` by design, because this one-shot CLI observation is not a signed tenant/source readback.

## Explicit commercial truth

The exercise improves the technical feasibility of the proposed premium Empire AI flagship. It does **not** establish a £250k independently appraised asset price, a paid customer, human consciousness, actual revenue, or a market-tested consumer assistant.

One EmpireOS. One PRIME. One original Voice Lab. One original ASTRA/EmpireDB owner authority. No new production activation.


## Validated original-system engineering result

**1,128 scoped regression tests passed** on the isolated original research worktree, including the new 28 local timer tests and existing Voice Lab, Decision Judge, source/CRM/Quant, AGI, Founder, PRIME and Digital Twin tests. The one warning was inherited from Starlette/anyio. This was not a full repository-wide suite or a production owner approval.

The genuine installed local Kokoro/Whisper experiment returned **REAL_LOCAL_SYNTHETIC_TIMER_EXPIRED_ONCE**, acknowledged exactly one sink event, and observed zero replay after polling again. The experiment ran within **18.105 seconds** and required no local llama.cpp generation. This evidence does not establish user-facing delivery, timer durability, voice cancellation or commercially paid operation. All live deployment and data/source authority remain HOLD.
