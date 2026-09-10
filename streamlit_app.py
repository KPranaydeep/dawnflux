"""Dawnflux: Streamlit = brain; Android (later) = instrument. No LLM."""
import io
import os
from datetime import datetime, time, timedelta
from uuid import uuid4
import pandas as pd
import streamlit as st
from src.database import Database
from src.exposure import manual_session, summarize_sessions, daily_exposure
from src.sleep import sleep_duration
from src.statistics import pair_days, window_statistics, correlation, exposure_bands, rolling_sleep
from src.optimization import estimate_target
from src.validation import LIGHT_COLUMNS, SLEEP_COLUMNS

st.set_page_config(page_title='Dawnflux', page_icon=':material/wb_sunny:', layout='centered')
st.title('Dawnflux')
st.caption('Personal morning-light experiments · deterministic analysis · no LLM')

# Only an operator-controlled environment variable enables shared persistent storage.
# Public deployments default to a private SQLite connection for each browser session.
db_path = os.environ.get('DAWNFLUX_DB_PATH', ':memory:')
if 'db' not in st.session_state:
    st.session_state.db = Database(db_path)
db = st.session_state.db
settings = db.settings()
today = pd.Timestamp.now(tz=settings['timezone']).date()
if db_path == ':memory:':
    st.info('Private temporary session. Download a JSON backup before closing or refreshing this tab. Restore it under Import / export next time.')
else:
    st.caption('Private local database enabled. Export regularly for backup.')
if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))
page = st.selectbox('Workspace', ['Dashboard', 'Morning light', 'Sleep', 'Import / export', 'Settings', 'Methods'], key='page')


def saved(message):
    st.session_state.notice = message
    st.rerun()


def local_timestamp(day, clock):
    # tz_localize rejects nonexistent/ambiguous DST wall times instead of guessing.
    return pd.Timestamp(datetime.combine(day, clock)).tz_localize(settings['timezone'], ambiguous='raise', nonexistent='raise')


if page == 'Settings':
    st.subheader('User settings')
    with st.form('settings'):
        timezone = st.text_input('Timezone (IANA name)', value=settings['timezone'])
        wake = st.time_input('Usual wake time', value=time.fromisoformat(settings['wake_time']))
        sleep_target = st.number_input('Sleep target (hours)', 1.0, 16.0, float(settings['sleep_target']), .25)
        initial = st.number_input('Initial morning-light target (lux·minutes)', 1.0, 10000000.0, float(settings['initial_target']), 100.0)
        st.caption('10,000 is a setup placeholder, not a recommended biological dose. Choose your own experimental baseline.')
        if st.form_submit_button('Save settings'):
            try:
                db.save_settings(dict(timezone=timezone, wake_time=wake.isoformat(), sleep_target=sleep_target, initial_target=initial))
                saved('Settings saved.')
            except (ValueError, KeyError) as exc:
                st.error(str(exc))

elif page == 'Morning light':
    st.subheader('Record morning light')
    st.caption('Manual entry assumes a constant average lux for the duration. Import timestamped sensor readings for measured sessions.')
    with st.form('light'):
        day = st.date_input('Session date', today)
        wake_clock = st.time_input('Actual wake time', time.fromisoformat(settings['wake_time']))
        start_clock = st.time_input('Session start time', time(7, 30))
        duration = st.number_input('Duration (minutes)', 1.0, 1440.0, 20.0)
        lux = st.number_input('Estimated average lux', 0.0, 1000000.0, 500.0)
        target = st.number_input('Session target (lux·minutes)', 1.0, 10000000.0, float(settings['initial_target']))
        if st.form_submit_button('Save light session'):
            try:
                frame = manual_session(str(uuid4()), local_timestamp(day, wake_clock), local_timestamp(day, start_clock), duration, lux, target)
                db.import_batch(light=frame)
                saved('Morning-light session saved. Back it up under Import / export.')
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
    st.dataframe(summarize_sessions(db.read('light')), hide_index=True)

elif page == 'Sleep':
    st.subheader('Record a sleep result')
    st.caption('Date means the day you woke up. Yesterday’s morning light is paired with this sleep result. Duration is elapsed onset-to-wake time; awake periods are not subtracted.')
    with st.form('sleep'):
        day = st.date_input('Wake date', today)
        bed_day = st.date_input('Bedtime date', today - timedelta(days=1))
        bed_clock = st.time_input('Bedtime', time(22, 30))
        onset_day = st.date_input('Sleep onset date', today - timedelta(days=1))
        onset_clock = st.time_input('Sleep onset', time(23, 0))
        wake_clock = st.time_input('Wake time', time.fromisoformat(settings['wake_time']))
        has_score = st.checkbox('Include a sleep score')
        score = st.number_input('Sleep score (0–100, use one consistent source)', 0.0, 100.0, 75.0)
        notes = st.text_area('Notes (caffeine, illness, travel, other changes)')
        if st.form_submit_button('Save sleep result'):
            try:
                bed, onset, wake = local_timestamp(bed_day, bed_clock), local_timestamp(onset_day, onset_clock), local_timestamp(day, wake_clock)
                record = dict(date=day.isoformat(), bedtime=bed.isoformat(), sleep_onset=onset.isoformat(), wake_time=wake.isoformat(),
                              sleep_duration=sleep_duration(onset, wake), sleep_score=score if has_score else None,
                              sleep_regularity=None, notes=notes)
                db.import_batch(sleep=pd.DataFrame([record]))
                saved('Sleep result saved. Back it up under Import / export.')
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
    st.dataframe(db.read('sleep'), hide_index=True)

elif page == 'Import / export':
    st.subheader('Import records')
    kind = st.selectbox('Import format', ['JSON backup', 'Morning light CSV', 'Sleep CSV'])
    upload = st.file_uploader('Choose a file', type=['csv', 'json'], max_upload_size=20)
    st.caption('Imports are atomic. Identical re-imports do not create duplicates; conflicting records are rejected. Keep each sensor session complete in one file.')
    if st.button('Import file', disabled=upload is None):
        if upload is not None:
            try:
                if upload.size > 20 * 1024 * 1024:
                    raise ValueError('Maximum file size is 20 MB.')
                text = upload.getvalue().decode('utf-8-sig')
                if kind == 'JSON backup':
                    db.import_json(text)
                else:
                    frame = pd.read_csv(io.StringIO(text), dtype={'session_id': str, 'date': str}, keep_default_na=False,
                                        na_values=[''])
                    db.import_batch(**{'light' if kind == 'Morning light CSV' else 'sleep': frame})
                saved('Import complete.')
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                st.error(f'Import rejected: {exc}')
    st.subheader('Export and backup')
    st.download_button('Download complete JSON backup', db.export_json(), 'dawnflux-backup.json', 'application/json')
    for kind, columns in [('light', LIGHT_COLUMNS), ('sleep', SLEEP_COLUMNS)]:
        frame = db.read(kind)
        st.download_button(f'Download {kind} CSV', frame.to_csv(index=False), f'dawnflux-{kind}.csv', 'text/csv')
        st.download_button(f'Download empty {kind} CSV template', pd.DataFrame(columns=columns).to_csv(index=False), f'{kind}-template.csv', 'text/csv')
        with st.expander(f'Raw {kind} data'):
            st.dataframe(frame, hide_index=True)

elif page == 'Dashboard':
    light, sleep = db.read('light'), db.read('sleep')
    as_of = st.date_input('Analysis through', today)
    pairs = pair_days(light, sleep)
    suggestion = estimate_target(pairs, settings['initial_target'], settings['sleep_target'], as_of)
    with st.container(horizontal=True):
        st.metric('Suggested target (lux·min)', f"{suggestion['target']:,.0f}", border=True)
        st.metric('Paired days / 28', str(suggestion['n']), border=True)
        st.metric('Sleep target (hours)', f"{settings['sleep_target']:.2f}", border=True)
    st.write(f"**Evidence: {suggestion['confidence']}**")
    st.write(suggestion['reason'])
    st.caption('Suggestion is anchored to your initial target; rerunning does not increase it. Manual and good-quality sessions qualify. Gapped/poor sessions remain in descriptive totals only.')
    if light.empty or sleep.empty:
        st.info('Start with Settings, then enter or import morning light and the following night’s sleep. Missing days are not treated as zero exposure.')
    st.subheader('7 / 14 / 28-day statistics')
    daily = daily_exposure(light)
    stats = pd.concat([window_statistics(sleep, as_of), window_statistics(daily, as_of)], ignore_index=True)
    st.dataframe(stats, hide_index=True)
    st.caption('Calendar windows end on the selected date. n is the number of recorded days, not the window length. q25/q75 describe the middle half of observations.')
    visible_sleep = sleep[pd.to_datetime(sleep.date) <= pd.Timestamp(as_of)]
    if not visible_sleep.empty:
        st.subheader('Sleep duration and rolling median')
        chart = visible_sleep[['date', 'sleep_duration']].copy()
        chart['date'] = pd.to_datetime(chart.date)
        chart = chart.set_index('date').sort_index()
        chart['7-day median'] = rolling_sleep(visible_sleep).sleep_duration
        st.line_chart(chart, y_label='Hours')
        st.subheader('Sleep regularity proxy')
        st.line_chart(visible_sleep.set_index('date')[['sleep_regularity']], y_label='0–100 proxy')
    visible_daily = daily[pd.to_datetime(daily.date) <= pd.Timestamp(as_of)]
    if not visible_daily.empty:
        st.subheader('Daily exposure')
        st.bar_chart(visible_daily, x='date', y='dose', y_label='Lux·minutes')
    recent = pairs[(pd.to_datetime(pairs.outcome_date) > pd.Timestamp(as_of) - pd.Timedelta(days=28)) &
                   (pd.to_datetime(pairs.outcome_date) <= pd.Timestamp(as_of))]
    st.subheader('Exposure dose and timing · last 28 days')
    if not recent.empty:
        st.dataframe(exposure_bands(recent, settings['initial_target']), hide_index=True)
        outcome = st.selectbox('Outcome', ['sleep_duration', 'sleep_score', 'sleep_regularity'])
        for x, label in [('dose', 'Exposure (lux·minutes)'), ('minutes_after_waking', 'First session start (minutes after waking)')]:
            assoc = correlation(recent, x, outcome)
            st.write(f"**{label}** · n={assoc['n']} · Spearman ρ=" + ('unavailable' if assoc['rho'] is None else f"{assoc['rho']:.2f}"))
            st.caption(assoc['reason'])
            st.scatter_chart(recent, x=x, y=outcome, x_label=label)
        with st.expander('Paired evidence table'):
            st.dataframe(recent, hide_index=True)
    else:
        st.info('No eligible exposure / next-night sleep pairs in this window yet.')
    sessions = summarize_sessions(light)
    if not sessions.empty:
        st.subheader('Measurement quality')
        st.dataframe(sessions.groupby('measurement_quality').size().rename('sessions').reset_index(), hide_index=True)

else:
    st.subheader('Inspectable methods')
    st.markdown('''
* **Dose:** trapezoidal sum of adjacent lux readings × elapsed minutes. Gaps over 120 seconds contribute zero; gapped/poor sessions are excluded from associations and suggestions. Manual entries use average lux × minutes.
* **Pairing:** morning exposure on date D predicts the sleep record with wake date D+1. No imputation for missing exposure or sleep days.
* **Sleep duration:** elapsed hours from sleep onset to waking. Score is optional (0–100).
* **Regularity proxy:** 100 minus the average onset/wake clock-time shift (minutes) from the previous consecutive day, clipped at zero. Midnight wraps correctly. This is not the validated Sleep Regularity Index.
* **Statistics:** means, medians, interquartile ranges and sample counts in calendar windows; seven-day rolling medians; Spearman rank correlations with at least seven nonconstant pairs.
* **Suggestion:** at least 21 pairs in 28 days, seven nights within sleep target −0.5 to +1 hours, and four distinct doses. Compare low/high dose groups in each 14-day half, requiring at least three nights per group and a consistent ≥20 percentage-point success-rate advantage. Reject comparisons with median timing differences over 30 minutes. Use median successful dose, capped at ±10% of the initial target. Confidence stays low because this is observational.

Lux·minutes measures photopic illuminance over time, not retinal or melanopic exposure. These personal associations do not establish causation or an optimal medical dose. The app does not operate a phone sensor or measure light with the browser. The later native Android client will export this same contract.
''')
    for module in ['exposure', 'sleep', 'statistics', 'optimization', 'validation']:
        with st.expander(f'Calculation source: {module}.py'):
            from pathlib import Path
            st.code((Path(__file__).parent / 'src' / f'{module}.py').read_text(encoding='utf-8'), language='python')
