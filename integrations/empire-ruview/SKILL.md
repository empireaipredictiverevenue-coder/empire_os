---
name: empire-ruview
description: Empire OS wrapper around ruvnet/RuView (WiFi-DensePose). Camera-free spatial intelligence — presence, breathing, heart rate, fall risk, occupancy. ESP32 sensors + Home Assistant / Matter / Apple Home integrations. Wire into Empire OS IoT + smart-building revenue verticals.
license: MIT
---

# Empire RuView

Wire the RuView repo (https://github.com/ruvnet/RuView) — camera-free RF perception
system using commodity WiFi signals (Channel State Information from ESP32 sensors) —
into Empire OS as a service.

## What it detects (from RuView upstream)

- Presence and occupancy (through walls, dark, no cameras)
- Vital signs: breathing rate, heart rate, contactless
- 10 inferred semantic states (per room per node):
  - someone-sleeping
  - possible-distress
  - room-active
  - elderly-inactivity-anomaly
  - meeting-in-progress
  - bathroom-occupied
  - fall-risk-elevated
  - bed-exit
  - no-movement
  - multi-room-transition

## Empire OS revenue integration

Smart-building verticals that already have buyers:
- elder_care_facility — fall-risk monitoring, occupancy tracking
- office_management — meeting-room utilization, occupancy
- hotel_chain — occupancy, no-movement alerts, distress detection
- insurance_underwriting — risk scoring via vital signs baseline

## Setup

Cloned at `/root/empire_os/integrations/RuView/`.

### Production Rust pipeline
```bash
cd /root/empire_os/integrations/RuView/v2
cargo build --release
cargo test --workspace --no-default-features
```

### Python reference pipeline
```bash
cd /root/empire_os/integrations/RuView/archive/v1
python -m pytest tests/ -x -q
python data/proof/verify.py  # deterministic proof: VERDICT: PASS
```

### ESP32 firmware
```bash
cd /root/empire_os/integrations/RuView/firmware/esp32-csi-node/
# See README for port/target — verify real boot log before claims
```

### Home Assistant integration
```bash
# Drop into HA with one --mqtt flag, or pair as Matter Bridge
# 21 entities per node + 3 starter HA Blueprints
```

## Empire OS hub integration

Add `/v1/ruview/sense` endpoint that:
- Accepts `{room_id, sensor_count, duration_sec}`
- Calls RuView Rust binary (via subprocess)
- Returns semantic state list + confidence scores

## Empire OS lane activation

Activate empty lanes:
- elder_care_facility (N metros, $2,399/seat)
- office_iot_monitoring (N metros, $599/seat)
- hotel_chain_iot (N metros, $999/seat)

## Caveats (per upstream CLAUDE.md)

- Don't present WiFi sensing as camera-grade
- Don't echo/commit WiFi passwords or secrets
- Don't merge firmware without real boot log on real silicon
- Don't report a PCK without its mean-pose baseline