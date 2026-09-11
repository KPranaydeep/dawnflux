# Dawnflux for Android

Native, offline morning-light recorder. Android 8+ (API 26), target SDK 36. Intended initial handset: OnePlus Nord 5, which lists an ambient-light sensor in its [official specifications](https://www.oneplus.in/nord-5/specs). Real screen-off behavior must still be verified on the handset.

## Use it

1. Install the APK on the phone. The initial APK is a debug-signed personal testing build, not a Play Store release.
2. Open Dawnflux. It displays the sensor name, wake-up capability and maximum lux range. If no sensor is exposed by Android, recording is unavailable.
3. Allow notifications. Both **Light session progress** and **Target and recording alerts** must be enabled.
4. Enter your actual wake time today and the target from your Dawnflux dashboard. The prefilled 10,000 lux·minutes is only a placeholder.
5. Tap **Start light session**. Take the phone outside with its light sensor uncovered. The gauge shows accumulated lux·minutes / target; it is not a physiological battery or vitamin D estimate.
6. Lock the screen if desired. A foreground notification shows progress and provides **Stop**. Keep the phone out of your pocket. The app holds a bounded partial wake lock only during the explicit session.
   The app and notification show **ETA**: remaining lux·minutes divided by the latest measured lux. It updates with real readings and assumes the light stays constant. Dark, stale or unreliable readings do not produce an ETA. Estimates may exceed the two-hour recording limit; they do not extend the session or add unmeasured exposure.
7. The target alert fires once per session. Recording continues until you tap **Stop and save**, or the two-hour cap is reached.
8. Choose a saved session and save CSV or JSON using Android's document picker. Upload it in Streamlit's **Import / export** page: choose **Morning light CSV** or **JSON backup / Android session**.
9. Record the following night's sleep in Streamlit to build the exposure/outcome evidence. Android records light only.

The app does not need Streamlit, Chrome, a server, an account, or network connectivity to record. It has no Internet permission. Data stays in app-private SQLite storage until you explicitly export it. Android automatic backup is disabled. Export before uninstalling, clearing storage or switching signing keys. Debug APKs built on different CI machines can have different signatures; keep exports before replacing a test build. Do not use a debug APK as a long-term signed production distribution.

## First OnePlus test

Record for 2–3 minutes with the screen on, then 2–3 minutes locked, then stop. Inspect/export the session: readings should continue and have no gaps over 120 seconds. Cover/uncover the sensor to confirm readings respond. If delivery pauses, open **Battery / background settings** and allow background activity for Dawnflux as available in your OxygenOS version; repeat the test. A foreground service cannot guarantee every vendor's screen-off sensor behavior.

No sun-gazing or special exposure duration is required to test the sensor. The readings describe the light at the handset, which may differ from light at your eyes.

## Implementation

* Java 17, native Android widgets, no WebView and no ML/LLM.
* `LightService`: user-initiated `specialUse` foreground service, ongoing notification, stop action, target alert, bounded CPU wake lock. No boot receiver and `START_NOT_STICKY`: it never silently resumes an interrupted experiment.
* A new app process marks previously active records interrupted/poor. Export retains actual samples; missing time is never reconstructed.
* `TYPE_LIGHT` may be on-change. The service re-registers every ten seconds to request a fresh activation event, rather than manufacturing samples from cached lux. Hardware/firmware may not deliver an activation event as expected; freshness is displayed, and two minutes without a reading stops the session as poor.
* Accepts current sensor events at most once per second. Rejects negative/nonfinite lux, stale/batched events and events predating start. Sensor saturation/unreliable accuracy marks the session poor.
* The wall timestamp is anchored once to the monotonic clock. Device wall-clock adjustments during a session do not add/subtract exposure. Export uses the wake timestamp's fixed offset for a consistent local session date.
* `Dose`: trapezoidal integration in elapsed milliseconds; intervals >120,000 ms contribute zero. This matches Python's v1 rule.
* SQLite sample insertion and quality updates are transactional. A stopped session requires ≥2 real samples for export. Start/end are the first/last sample instants, not button-tap times.
* CSV contains exactly the original 12 light fields. JSON is `{ "schema_version": 1, "morning_light": [...] }`; the importer preserves existing sleep and settings.
* No automatic transmission or background sync. Transfer is deliberately via user-selected files.

Android's `specialUse` type requires an explanatory subtype and is subject to review if later distributed on Play. This implementation does not claim Play approval. See [foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types), [wake-lock guidance](https://developer.android.com/develop/background-work/background-tasks/awake), and [on-change sensor reporting](https://source.android.com/docs/core/interaction/sensors/report-modes).

## Build and test

Install JDK 17, Android SDK 36 and Gradle 8.13 (or open this directory in a compatible Android Studio). Set `ANDROID_HOME` or an untracked `local.properties` containing `sdk.dir=...`.

```text
gradle -p android testDebugUnitTest lintDebug assembleDebug
```

From inside this directory omit `-p android`. Output: `app/build/outputs/apk/debug/app-debug.apk`. The GitHub **Android APK** workflow builds the APK, runs JVM tests and Android lint, then imports actual Java-produced CSV and JSON fixtures using the Python database layer. Artifacts are downloadable from the successful workflow run.

Hardware tests remain necessary: sensor presence, saturation, notifications denied/disabled, lock screen, battery saver, kill/force-stop, clock change, background restrictions, target reached once, manual stop, two-hour cap, export/re-import. Automated build tests are not evidence of OnePlus screen-off sensor reliability.
