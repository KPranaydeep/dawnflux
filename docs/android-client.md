# Stage 2: native Android measurement client

The instrument operates independently of Streamlit. No browser sensor API or website keep-alive is part of the design. The implementation is now in `android/`; see [build, use and validation instructions](../android/README.md). It uses native Java and SQLite rather than the originally considered Kotlin/Room stack. Real-device behavior has not yet been verified on the user's OnePlus Nord 5.

## Responsibilities

1. User explicitly starts a session after receiving/entering wake time and target (initially manual entry; a versioned session-request import can follow).
2. Native client checks for `Sensor.TYPE_LIGHT`; if absent, report unsupported and never fabricate readings.
3. Persist timestamped lux samples locally using SQLite, with the wall timeline derived from monotonic sensor time. Use stable UUID session IDs and transactional sample writes.
4. Compute cumulative lux·minutes using the v1 trapezoidal rule. Persist every reading, including zero lux. Do not add unobserved time.
5. Start an Android foreground service from the visible activity, with an ongoing notification showing dose, target, elapsed session time, and a Stop action.
6. Keep the explicitly started session working with the screen locked. Assess whether each device's light sensor is a wake-up sensor; use an appropriately bounded partial wake lock if required. Foreground service presence alone does not guarantee sensor delivery. Detect/report gaps and interrupted sessions.
7. Notify once when the target is crossed, preserving the recording until the user stops it (or a clearly selected auto-stop setting). Handle notification permission denial visibly before session start.
8. Finalize session_start/end and quality, then export complete CSV or Dawnflux v1 JSON using the system document picker/share sheet. Never export partial sessions as good quality.
9. User uploads the export to Streamlit. Authentication-backed sync can be added later without changing the raw contract.

## Contract details

The [README](../README.md#shared-contract-version-1) is authoritative. Every finalized reading has exactly the 12 light fields. Accumulate from monotonic elapsed time to avoid device clock adjustments; export an offset-aware wall-clock timeline consistent with that elapsed time. If clock changes make this impossible, flag interruption and split sessions rather than silently rewriting measured durations.

Raw endpoint `target_reached` is per-reading, not a final-session boolean repeated throughout. `measurement_quality` is final-session quality repeated throughout. A gap over 120 seconds adds zero dose and makes the session gapped/poor. Device-specific provenance/calibration may be retained privately in a separate sidecar; do not add extra CSV columns to v1.

## Implementation gate

The implemented service uses `specialUse` with an explicit subtype, foreground-service permissions, notification permission and a bounded wake lock. It starts from a visible activity. Public Play distribution would require a separate service-type review and release signing; the personal testing APK does not claim that review has happened.

Hardware acceptance tests must cover supported and missing sensors, bright-light saturation, timestamps/integration, lock screen, battery saver, process interruption, notification denial, target notification exactly once, user stop, clock/timezone changes, long gaps, and exported-file import into Dawnflux. Test real devices: emulator/screen-on tests cannot establish screen-off sensor reliability.
