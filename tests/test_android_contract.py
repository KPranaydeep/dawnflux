"""Run in Android CI against files emitted by the actual Java exporter."""
import os
from pathlib import Path
import pandas as pd
import pytest
from src.database import Database


@pytest.mark.skipif(not os.environ.get('ANDROID_CONTRACT_DIR'), reason='Requires Java-generated fixtures from Android build')
def test_java_exports_import_without_changes():
    root = Path(os.environ['ANDROID_CONTRACT_DIR'])
    json_db, csv_db = Database(), Database()
    json_db.import_json((root / 'android-session.json').read_text())
    csv_db.import_batch(light=pd.read_csv(root / 'android-session.csv'))
    pd.testing.assert_frame_equal(json_db.read('light'), csv_db.read('light'), check_dtype=False)
    data = json_db.read('light')
    assert data.cumulative_lux_minutes.tolist() == [0, 1000, 1000]
    assert data.measurement_quality.tolist() == ['gapped'] * 3


@pytest.mark.skipif(not os.environ.get('ANDROID_CONTRACT_DIR'), reason='Requires Java-generated fixtures')
def test_combined_android_export():
    root = Path(os.environ['ANDROID_CONTRACT_DIR'])
    content = (root / 'android-combined.json').read_text()
    db = Database()
    settings = db.settings()
    db.import_json(content)
    db.import_json(content)
    assert len(db.read('light')) == 3
    sleep = db.read('sleep')
    assert len(sleep) == 1
    assert sleep.iloc[0].sleep_duration == 8
    assert pd.isna(sleep.iloc[0].bedtime)
    assert sleep.iloc[0].sleep_score == 85
    assert db.settings() == settings
