from streamlit.testing.v1 import AppTest
from pathlib import Path


def test_empty_pages(monkeypatch):
    monkeypatch.delenv('DAWNFLUX_DB_PATH', raising=False)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'streamlit_app.py', default_timeout=20).run()
    assert not app.exception
    for page in ['Morning light', 'Sleep', 'Import / export', 'Settings', 'Methods', 'Dashboard']:
        app.selectbox(key='page').select(page).run()
        assert not app.exception, page


def test_entry_and_populated_dashboard(monkeypatch):
    monkeypatch.delenv('DAWNFLUX_DB_PATH', raising=False)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'streamlit_app.py', default_timeout=20).run()
    app.selectbox(key='page').select('Morning light').run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.session_state.db.read('light')) == 2
    app.selectbox(key='page').select('Sleep').run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.session_state.db.read('sleep')) == 1
    app.selectbox(key='page').select('Dashboard').run()
    assert not app.exception


def test_paired_dashboard(light, sleep, monkeypatch):
    from src.database import Database
    monkeypatch.delenv('DAWNFLUX_DB_PATH', raising=False)
    db = Database()
    db.import_batch(light, sleep)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'streamlit_app.py', default_timeout=20)
    app.session_state.db = db
    app.run()
    from datetime import date
    app.date_input[0].set_value(date(2026, 9, 10)).run()
    assert not app.exception

