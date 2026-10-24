# EmpireOS PRIME Flagship — Actual Offline Speech Round-Trip

Date: 24 October 2026
Status: Research-branch milestone only; original production, EmpireDB, Voice Gateway, AGI, Smart CRM and model parameters unchanged.
Objective: close one genuine low-risk **spoken** link in the original flagship, not build a second assistant.

## What really happened

The existing original `empire_os.voice_lab.SherpaKokoroTTS` **synthesized real PCM16 audio** from the fictional statement **"Set a timer for two minutes."** The existing original `SherpaWhisperSTT` **transcribed the synthesized audio**. A new deterministic, tightly bounded PRIME task recognizer parsed a 120-second timer and returned a safe explicit response. The **same original Kokoro speech model generated the answer audio**. No mocked recognition/synthesis in this real offline probe.

The local command, with a 65-second external OS-level deadline and nice priority 15, returned exit code 0 and:
- Total program elapsed: **16.85 s**
- Initial fictional TTS elapsed: **5.931 s**
- Original Whisper STT elapsed: **1.687 s**
- Fictional input audio: **51,630 bytes** of memory-only PCM16 16kHz
- Fictional spoken acknowledgement: **204,994 bytes** of memory-only PCM16 16kHz
- Recognised fictional timer duration: **120 seconds**
- Output status: `FICTIONAL_SPOKEN_ACK_AUDIO_VERIFIED_NOT_SCHEDULED`
- Actual timer scheduled: **false**
- Recorded/outbound customer data: **none**
- Real-world model generation and commercial outcomes: **not tested / unverified**

This is **one** real-speech-path proof with a synthetic recording, not a microphone experiment, streaming real voice test, multi-turn real-world reliability estimate, low-latency demonstration or completed consumer assistant action.

## What has been added

- `empire_os/prime_flagship_voice_task_rehearsal.py`: original Voice Lab STT/TTS injection, strictly bounded PCM16, deterministic timer intent parse and budget, reuse of existing AGI capability review, bounded reply with explicit *no timer scheduled* wording, TTS PCM16 validation, fail-closed high-risk intent/opt-out/emergency handling. It does **not** call the original generative LLM, legacy Vonage gateway, Supabase, any home device or notification scheduler.
- `scripts/rehearse_prime_flagship_speech_roundtrip_20261024.py`: one-shot real local Kokoro→Whisper→PRIME→Kokoro offline proof with process-level timeout and zero file persistence. Only fictional prompts are used.
- `tests/test_prime_flagship_voice_task_rehearsal.py`: artificial-audio stubs for the safety/edge cases and Founder output authority checks; these are separate from the measured real local speech result. Real speech was independently run through the CLI, not substituted with mocks.
- `empire_os/prime_digital_twin_cockpit.py`: privacy-minimal optional Founder projection of this research state, default `NOT_RUN` in its GET-only request. This is truthful: one manual CLI observation is not an authenticated persisted source feed available to the app at page render time.
- `apps/search-command-centre/src/lib/founder-api.ts`: types for the new read-only voice task projection.

## Risk and governance

The original AGI registry **does not yet authorise an actual timer executor** in this research path. The recognised command can only produce a spoken *simulation acknowledgement*, never a real timer confirmation. Explicit refusal/opt-out/emergency, unsupported additional commands, unrelated high-risk financial/device/contact instructions, unknown or excessive duration, malformed audio and malformed TTS output fail closed.

This is a measurement using the existing Voice Lab local speech assets without changing the legacy Voice Gateway. That gateway still references **Supabase**, whereas the canonical platform must be **EmpireDB PostgreSQL**; don't enable that route for flagship real users until original Voice/Data/Privacy/Security owners fix and independently verify the canonical backend and access authority.

The original llama.cpp language-generation endpoint remains independently unresolved: prior minimal 24-token fictional JSON request timed out after 15.04 seconds despite healthy /health and idle slot. Audio synthesis/recognition success does not prove local model generation.

## Next acceptance sequence, without feature loops

1. Original Voice owner: repeat this offline synthetic speech test multiple times, measure cold/warm p50/p95 and CPU footprint on isolated capacity; test accents, noise and adversarial refusals, then user-consented microphone input with bounded local processing and retention.
2. Original Scheduler/ASTRA owner: connect a real, test-only timer/reminder capability with signed user permission, cancellation, correct time zone and **verified delivery**. Do not claim scheduled/delivered until authentic source receipt exists.
3. Original Model owner: diagnose llama.cpp generation timeout; demonstrate independently measured bounded local utterance quality and fail-safe interruption without production inference disruption.
4. Original Security/Founder owner: private UI ingress, authentication and human mobile/desktop acceptance. This research change does not activate any public voice service.
5. Original Commercial owner: measure real consumer/enterprise utility and accepted proposals before asserting the target £250k flagship value.

A real synthetic offline speech round-trip is now proven; a functioning assistant with a delivered reminder and voice input from an actual user is not.

One EmpireOS. One original Voice Lab. One PRIME/Digital Twin. One canonical EmpireDB.


## Verified engineering acceptance on the research branch

- **1,100 scoped regressions passed**, including the original Voice Lab, Decision Judge, voice gateway, PRIME, original Digital Twin, AGI, Founder API, CRM/Quant and source-evidence contracts. There was one inherited Starlette/anyio deprecation warning. This is **not** the full repository suite or a production release.
- The original Search Command Centre `./node_modules/.bin/tsc --noEmit -p tsconfig.json` **passed** against the extended read-only Founder API response contract.
- Live speech-model synthetic round-trip was run independently using actual installed local model files with timeout/nice. It completed with exit code 0 and the measured timings and PCM16 byte counts documented above.
- The new original Founder cockpit projection intentionally remains `NOT_RUN` in GET-only requests; a standalone local experiment is not a signed, stored, tenant-bound provider receipt.
- Original production code, voice transport, canonical EmpireDB, Smart CRM, real user microphone, live schedule and external outbound were not changed.
