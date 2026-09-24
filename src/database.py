"""Private SQLite or per-browser-session in-memory SQLite. No global cache."""
import json
import sqlite3
import math
from numbers import Real
from pathlib import Path
import pandas as pd
from src.validation import (LIGHT_COLUMNS, SLEEP_COLUMNS, DEFAULT_SETTINGS,
                            validate_light, validate_sleep, validate_settings)
from src.sleep import add_regularity


def _same_records(left, right):
    """Compare complete sessions/days, ignoring only serialization differences."""
    if len(left) != len(right):
        return False
    if 'timestamp' in left:
        left = left.iloc[sorted(range(len(left)), key=lambda i: pd.Timestamp(left.iloc[i].timestamp))]
        right = right.iloc[sorted(range(len(right)), key=lambda i: pd.Timestamp(right.iloc[i].timestamp))]
    timestamps = {'timestamp', 'wake_time', 'session_start', 'session_end', 'bedtime', 'sleep_onset'}
    for a, b in zip(left.to_dict('records'), right.to_dict('records')):
        for key in a:
            x, y = a[key], b[key]
            if pd.isna(x) or pd.isna(y):
                if not (pd.isna(x) and pd.isna(y)):
                    return False
            elif key in timestamps:
                if pd.Timestamp(x) != pd.Timestamp(y):
                    return False
            elif isinstance(x, Real) and isinstance(y, Real):
                # Historical pandas JSON exports retain ten decimal places.
                if not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-9):
                    return False
            elif x != y:
                return False
    return True


class Database:
    def __init__(self, path=':memory:'):
        if path != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, record_key TEXT, payload TEXT, PRIMARY KEY(kind, record_key))')
        self.connection.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT)')

    def settings(self):
        row = self.connection.execute('SELECT payload FROM settings WHERE id=1').fetchone()
        return json.loads(row[0]) if row else DEFAULT_SETTINGS.copy()

    def save_settings(self, settings):
        settings = validate_settings(settings)
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO settings VALUES (1, ?)', (json.dumps(settings),))

    def read(self, kind):
        columns = LIGHT_COLUMNS if kind == 'light' else SLEEP_COLUMNS
        rows = self.connection.execute('SELECT payload FROM records WHERE kind=? ORDER BY record_key', (kind,)).fetchall()
        frame = pd.DataFrame([json.loads(row[0]) for row in rows], columns=columns)
        return add_regularity(frame) if kind == 'sleep' else frame

    def import_batch(self, light=None, sleep=None, settings=None, conflict_policy="reject"):
        """Atomic merge; compare whole sessions and never silently overwrite history."""
        if conflict_policy not in ('reject', 'keep_existing'):
            raise ValueError('Unknown conflict policy.')
        report = dict(added_light_sessions=0, added_sleep_days=0, unchanged=0, kept_conflicts=[])
        staged = []
        for kind, frame, validator in [('light', light, validate_light), ('sleep', sleep, validate_sleep)]:
            if frame is None or frame.empty:
                continue
            new = validator(frame)
            old = self.read(kind)
            # Regularity is derived from the complete timeline, not trusted input.
            if kind == 'sleep':
                new['sleep_regularity'] = None
                old['sleep_regularity'] = None
            keys = ['session_id', 'timestamp'] if kind == 'light' else ['date']
            group_key = 'session_id' if kind == 'light' else 'date'
            accepted = []
            for identity, incoming in new.groupby(group_key, sort=False):
                existing = old[old[group_key] == identity]
                if existing.empty:
                    accepted.append(incoming)
                    report['added_light_sessions' if kind == 'light' else 'added_sleep_days'] += 1
                elif _same_records(existing, incoming):
                    report['unchanged'] += 1
                elif conflict_policy == 'keep_existing':
                    report['kept_conflicts'].append(f'{kind}: {identity}')
                else:
                    raise ValueError(f'Conflicting {kind} record: {identity}. '
                                     'Choose "Keep existing records; import new days" to retain saved history and add new data.')
            new = pd.concat(accepted, ignore_index=True) if accepted else new.iloc[:0]
            combined = pd.concat([old, new], ignore_index=True)
            validator(combined)
            for record in json.loads(new.to_json(orient='records', double_precision=15)):
                key = json.dumps([record[k] for k in keys])
                staged.append((kind, key, json.dumps(record, allow_nan=False)))
        if settings is not None:
            settings = validate_settings(settings)
        with self.connection:
            self.connection.executemany('INSERT OR IGNORE INTO records VALUES (?, ?, ?)', staged)
            if settings is not None:
                self.connection.execute('INSERT OR REPLACE INTO settings VALUES (1, ?)', (json.dumps(settings),))

        return report

    def export_json(self):
        return json.dumps(dict(schema_version=1, settings=self.settings(),
            morning_light=json.loads(self.read('light').to_json(orient='records', double_precision=15)),
            sleep=json.loads(self.read('sleep').to_json(orient='records', double_precision=15))), indent=2, allow_nan=False)

    def import_json(self, content, conflict_policy="reject"):
        data = json.loads(content)
        if not isinstance(data, dict) or data.get('schema_version') != 1:
            raise ValueError('Expected Dawnflux schema_version 1 JSON backup.')
        if set(data) == {'schema_version', 'morning_light'}:
            # Android session envelope: importing exposure must not reset settings/sleep.
            if not isinstance(data['morning_light'], list) or not data['morning_light']:
                raise ValueError('Android export requires a nonempty morning_light array.')
            return self.import_batch(light=pd.DataFrame(data['morning_light']), conflict_policy=conflict_policy)
        if set(data) == {'schema_version', 'morning_light', 'sleep'}:
            if not isinstance(data['morning_light'], list) or not isinstance(data['sleep'], list):
                raise ValueError('Android export requires light and sleep arrays.')
            return self.import_batch(light=pd.DataFrame(data['morning_light']), sleep=pd.DataFrame(data['sleep']), conflict_policy=conflict_policy)
        if not {'morning_light', 'sleep', 'settings'}.issubset(data):
            raise ValueError('Backup requires morning_light, sleep and settings.')
        light = pd.DataFrame(data['morning_light']) if data['morning_light'] else pd.DataFrame(columns=LIGHT_COLUMNS)
        sleep = pd.DataFrame(data['sleep']) if data['sleep'] else pd.DataFrame(columns=SLEEP_COLUMNS)
        return self.import_batch(light, sleep, data['settings'], conflict_policy=conflict_policy)
