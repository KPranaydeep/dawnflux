"""Fail-closed Streamlit auth/storage bootstrap."""
import os
import streamlit as st
from src.database import Database
from src.identity import owner_id
from src.postgres import PostgresDatabase, StorageError


def _current_client(client, expected_type):
    """Rebind a pre-deployment session object without losing its SQLite data.

    Streamlit retains session_state objects across source-code reruns. Their
    class may belong to the previous module even though the page is updated.
    Both supported clients keep state in __dict__; no connection is reopened.
    """
    if type(client) is expected_type:
        return client
    if (type(client).__module__, type(client).__name__) != (expected_type.__module__, expected_type.__name__):
        raise StorageError('Storage client type changed unexpectedly. Export your data before reloading.')
    current = expected_type.__new__(expected_type)
    current.__dict__.update(client.__dict__)
    return current


def _is_postgres(client):
    return (type(client).__module__, type(client).__name__) == (PostgresDatabase.__module__, PostgresDatabase.__name__)


def open_storage():
    try:
        config = dict(st.secrets.get('storage', {}))
    except FileNotFoundError:
        config = {}
    mode = config.get('mode', 'temporary')
    if mode not in ('temporary', 'postgres'):
        st.error('Storage configuration is invalid. Contact the app owner.')
        st.stop()
    if mode == 'postgres':
        required = ('dsn', 'allowed_emails', 'oidc_issuer')
        if any(not config.get(key) for key in required) or 'auth' not in st.secrets:
            st.error('Private storage setup is incomplete. Sign-in and database settings are required.')
            st.stop()
        if not st.user.is_logged_in:
            st.info('Sign in to access your private, saved Dawnflux records.')
            if st.button('Sign in'):
                st.login()
            st.stop()
        try:
            owner = owner_id(dict(st.user), config['allowed_emails'], config['oidc_issuer'])
        except (PermissionError, ValueError):
            st.error('This signed-in account is not authorized for Dawnflux.')
            if st.button('Sign out'):
                st.logout()
            st.stop()
        if st.button('Sign out'):
            if 'db' in st.session_state:
                st.session_state.pop('db').connection.close()
            st.session_state.clear()
            st.logout()
            st.stop()
        # A changed identity/config always gets a fresh private snapshot.
        import hashlib
        key = ('postgres', owner, hashlib.sha256(config['dsn'].encode()).hexdigest())
        try:
            if st.session_state.get('_storage_key') != key:
                previous = st.session_state.pop('db', None)
                if previous is not None:
                    previous.connection.close()
                st.session_state.clear()
                st.session_state.db = PostgresDatabase(config['dsn'], owner)
                st.session_state._storage_key = key
            else:
                st.session_state.db = _current_client(st.session_state.db, PostgresDatabase)
                st.session_state.db.refresh()
        except StorageError as exc:
            st.error(str(exc))
            st.stop()
        db = st.session_state.db
        if db.updated_at:
            st.caption(f'Private cloud storage · saved through {db.updated_at:%Y-%m-%d %H:%M UTC} · revision {db.revision}')
        else:
            st.info('Private cloud storage connected. Import your existing backup or enter your first record.')
        return db
    # Existing temporary/local behavior remains available until cloud configuration
    # is installed. A postgres error never falls back into this branch.
    path = os.environ.get('DAWNFLUX_DB_PATH', ':memory:')
    if 'db' not in st.session_state:
        st.session_state.db = Database(path)
    if _is_postgres(st.session_state.db):
        st.session_state.pop('db').connection.close()
        st.session_state.clear()
        st.session_state.db = Database(path)
    st.session_state.db = _current_client(st.session_state.db, Database)
    if path == ':memory:':
        st.info('Private temporary session. Download a JSON backup before closing or refreshing this tab. Restore it under Import / export next time.')
    else:
        st.caption('Private local database enabled. Export regularly for backup.')
    return st.session_state.db
