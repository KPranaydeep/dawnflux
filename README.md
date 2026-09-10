# Dawnflux

Personal morning-light experimentation, with deterministic Python analysis and no LLM dependency.

**Streamlit = brain. Android = instrument. GitHub = source control. Local/exported data = experimental record.**

Stage 1 is implemented here. Stage 2 now includes a native Android measurement client under `android/`; real-device screen-off verification is still required.

## Run locally

Python 3.12 or later is recommended. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
$env:DAWNFLUX_DB_PATH = 'data/dawnflux.sqlite3'
.\.venv\Scripts\python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
DAWNFLUX_DB_PATH=data/dawnflux.sqlite3 .venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

The database path is an operator setting, never a browser input. Persistent mode is for a trusted, single-user deployment. It is not a multi-user authenticated service. Do not expose persistent mode publicly. Default mode (without `DAWNFLUX_DB_PATH`) uses a separate in-memory SQLite database per browser session. No private data is cached globally.

1. Open **Settings** and choose timezone, usual wake time, desired sleep duration and initial light target.
2. Enter average lux and duration in **Morning light**, or import raw readings.
3. Record the following night's sleep under its **wake date**.
4. Open **Dashboard** for calendar-window statistics, charts, associations and a suggested target with its evidence.
5. Download a full JSON backup under **Import / export**. It includes both datasets and settings. Restore it on the next visit.

The initial 10,000 lux·minute value is an editable setup placeholder, not a recommended dose. Native controls and a single-column flow support Android Chrome. The web app never requests ambient-light access.

## Storage and privacy

* Local SQLite files, exports, secrets and virtual environments are ignored by Git. Only `data/.gitkeep` is tracked in `data/`.
* In default session mode, records survive Streamlit reruns but can be lost on browser reload, disconnection, server restart or tab close. Download JSON **before** leaving. The downloaded file is the durable experimental record.
* On Community Cloud, uploaded/entered data is processed on Streamlit's server. Session isolation is not encryption or an account-based private data store. Use local mode if that processing is unsuitable.
* Community Cloud's runtime disk is not treated as a durable health-data store. This version does not promise automatic cloud persistence or synchronization.
* Never commit personal records, backups or `.streamlit/secrets.toml`. If adding durable hosted storage later, first add authentication, per-user authorization and backups.
* Imports are all-or-nothing. Identical records are ignored; conflicting records are rejected without overwriting. To correct records in V1, edit an exported file and restore it into a fresh temporary session or a new private database path. Keep the original backup.

## Deploy Stage 1 to Streamlit Community Cloud

Destination: **KPranaydeep/dawnflux**, branch **main**, entrypoint **streamlit_app.py**.

1. Authenticate GitHub CLI as KPranaydeep: `gh auth login --hostname github.com`.
2. If needed, create the repository, then commit only source/config/tests/docs:

   ```powershell
   git add .gitignore README.md requirements.txt requirements-dev.txt streamlit_app.py src tests docs .streamlit/config.toml .github/workflows/tests.yml data/.gitkeep
   git commit -m "Build Dawnflux deterministic Streamlit analysis application"
   gh repo create KPranaydeep/dawnflux --public --source . --remote origin --push
   ```

   If the repository already exists, use its existing remote and `git push -u origin main` instead of creating a duplicate. Inspect `git status` before committing.

3. Sign in to [Streamlit Community Cloud](https://share.streamlit.io), review its terms, choose **Create app**, then select the repository, `main` and `streamlit_app.py`.
4. Select Python **3.12** in advanced settings. No API keys, model service, database secrets or sensor permissions are required. Leave `DAWNFLUX_DB_PATH` unset.
5. Deploy. Open the resulting URL in Android Chrome; test manual entry, JSON download and restoration. Subsequent pushes to the chosen branch update the app.

See the [official deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Shared contract, version 1

CSV files must use exactly the column names below. Download empty templates from the application. JSON backups have `schema_version: 1`, `settings`, `morning_light` and `sleep` keys. The latter two are arrays of records with these same fields. JSON null and blank CSV fields represent missing optional values.

### Morning light: one row per reading

```text
session_id,date,timestamp,lux,cumulative_lux_minutes,wake_time,session_start,session_end,minutes_after_waking,target_lux_minutes,target_reached,measurement_quality
```

| Field | Meaning |
| --- | --- |
| session_id | Stable string ID (UUID recommended); maximum 128 characters |
| date | Local wake/session-start date, YYYY-MM-DD |
| timestamp | ISO 8601 datetime with explicit UTC offset |
| lux | Finite nonnegative photopic illuminance |
| cumulative_lux_minutes | Trapezoidal integral from the first reading; starts at zero |
| wake_time | Actual wake datetime, with offset |
| session_start / session_end | Datetimes of first/last reading; repeated on every row |
| minutes_after_waking | Elapsed minutes between actual wake and session start, constant per session |
| target_lux_minutes | Positive session target, constant per session |
| target_reached | Boolean **at this reading**, cumulative dose ≥ target |
| measurement_quality | `good`, `manual`, `gapped` or `poor`, constant per finalized session |

At least two unique readings are required. Import finalized complete sessions, not incremental fragments. Sort by actual instant before integration. Timestamps must include offsets, including when crossing DST. Session length must be positive and at most 24 hours; start must follow wake. Sessions may touch but cannot overlap. `good` means contract-valid sensor readings without long gaps; it does not assert sensor calibration.

For sensor data, intervals **over 120 seconds contribute zero dose** and require `gapped` or `poor` quality. All other intervals contribute `(lux_previous + lux_current) / 2 * elapsed_seconds / 60`. Android must use this same integration policy to produce importable cumulative values. Comparisons allow 0.01 lux·minutes absolute or 1e-5 relative numeric tolerance.

Manual average-lux entries produce exactly two synthetic endpoints with `measurement_quality=manual`; their interval is integrated irrespective of gap length. They are clearly estimates, not recorded sensor observations. Do not relabel sparse sensor data as manual to avoid the gap checks.

### Sleep: one row per wake date

```text
date,bedtime,sleep_onset,wake_time,sleep_duration,sleep_score,sleep_regularity,notes
```

* `date` is the local **wake date**, YYYY-MM-DD.
* `bedtime`, `sleep_onset`, `wake_time` are explicit-offset ISO datetimes, with bedtime ≤ onset < wake within 24 hours.
* `sleep_duration` is elapsed onset-to-wake **hours** (awake periods are not subtracted).
* `sleep_score` is optional, 0–100. Use the same source/scale throughout an experiment.
* `sleep_regularity` is optional on import and always recomputed on read/export from the complete timeline.
* `notes` is optional free text. Sleep data models one principal episode per wake date; naps are not modeled.

Timezone settings apply to new manual entries; changing settings does not reinterpret historic timestamps. Ambiguous/nonexistent DST manual times are rejected; import explicit-offset timestamps for those cases.

## Analysis and limitations

Source modules are also viewable in the app's **Methods** page.

* `src/exposure.py`: gap-aware trapezoidal integration, manual estimates, session totals and daily totals. Missing days are never zero-filled. Non-overlapping sessions are summed; timing is the first session's start after waking.
* `src/sleep.py`: duration and regularity proxy. For consecutive wake dates only: `max(0, 100 - mean(onset_clock_shift_minutes, wake_clock_shift_minutes))`, using the shortest distance around midnight. This is **not** the validated Sleep Regularity Index.
* `src/statistics.py`: means, medians, quartiles, counts for inclusive 7/14/28-calendar-day windows; seven-day rolling medians with at least two observations. Exposure on D pairs only with wake-date D+1. This fixed lag is intended for conventional nighttime sleep, not shift-work or polyphasic schedules.
* Exposure bands are below 75%, 75–125%, and ≥125% of the initial target. Boundary 75% belongs to the middle band; 125% belongs to the upper band.
* Spearman correlations require at least seven complete pairs and nonconstant variables. Missing scores/regularity are removed pairwise. No p-value is advertised as causal proof. Serial dependence, seasonality, caffeine, illness, activity and self-report bias remain uncontrolled.
* `src/optimization.py`: last 28 outcome dates; ≥21 paired days; ≥7 successful nights (sleep target −0.5 to +1 hour); ≥4 distinct doses; ≥5 observations each below/equal vs above median dose. Reject groups whose median exposure timings differ by >30 minutes. Each 14-day half must contain ≥3 nights in each dose group and ≥20 percentage-point success-rate advantage in the candidate direction. Candidate is median dose on successful nights, capped at ±10% of the initial target. Estimates never automatically update settings and never ratchet on rerun. Confidence remains **low, observational**, even when criteria pass.
* Gapped/poor sessions remain in descriptive exposure totals but are excluded from association/target data. Eligible daily totals can therefore differ from all-session totals; the raw table exposes quality.

These thresholds are explicit experimental heuristics, not clinically validated rules or a black-box model. Lux·minutes does not measure melanopic/retinal exposure or account for spectral composition, gaze or sensor placement. A personal association does not establish an optimal medical dose.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q
```

Tests cover integration and gaps, midnight/DST, calendar windows, next-night pairing, target safeguards, atomic imports, idempotency, persistence, session isolation and Streamlit page/form flows. Fixtures are synthetic; there are no personal health records in the repository. GitHub Actions runs the suite on Python 3.12.

## Stage 2

See [Android installation and recording instructions](android/README.md). The client records offline, displays target progress, runs an explicitly started foreground session with a bounded wake lock, alerts at the target, and exports CSV/JSON for this dashboard. See [integration notes](docs/android-client.md) for the architectural boundary. Android JSON session imports preserve your existing settings and sleep records.
