# Permanent private storage with Neon

This connects the existing Streamlit application to Neon PostgreSQL. Data survives browser refresh, Streamlit sleep/redeploy and device changes. The Android recorder is unchanged; its CSV/JSON imports still work.

## Before switching

Download a complete JSON backup from every temporary browser session you want to retain. Temporary data cannot be recovered after its session disappears. Enabling sign-in starts a new session; restore the backup after you sign in.

## 1. Prepare Neon

Use a dedicated database/branch for Dawnflux in your existing Neon project. In its SQL Editor, run [001_private_storage.sql](../migrations/001_private_storage.sql). It only creates the two Dawnflux tables; it does not drop or replace existing data.

Create a dedicated application role in Neon, rather than using your database owner credential in Streamlit. Grant it access using your actual database and role names:

```sql
GRANT CONNECT ON DATABASE neondb TO dawnflux_app;
GRANT USAGE ON SCHEMA public TO dawnflux_app;
GRANT SELECT, INSERT, UPDATE ON dawnflux_owners, dawnflux_records TO dawnflux_app;
```

Create/set the role's password privately through Neon. Copy the application's **pooled connection string** from Neon's Connect panel. The app enforces TLS with certificate and hostname verification. The URL never goes into source control, browser widgets or normal error output. It works with transaction pooling; no persistent connection is cached.

## 2. Configure Google sign-in

In a Google Cloud project, configure Google Auth Platform and create an OAuth client of type **Web application**. Enable the identity scopes `openid`, `email`, and `profile`. Set this exact authorized redirect URI:

```text
https://dawnflux.streamlit.app/oauth2callback
```

If the consent screen is in Testing mode, add your Google account as a test user. Keep the client ID and client secret private. Other OIDC providers can be used if they issue stable `sub`, `iss`, `email` and boolean `email_verified` claims; update both issuer and metadata URL.

## 3. Install Streamlit Secrets

Open Dawnflux's Community Cloud settings → Secrets. Use [.streamlit/secrets.toml.example](../.streamlit/secrets.toml.example) as the template and replace all placeholders privately. The required values are:

* Neon pooled connection string, using the restricted application role.
* Your allowed Google email address (only these accounts may enter).
* Google OAuth client ID and client secret.
* A long random cookie secret. Generate locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste it into the private Secrets field.

Set `storage.mode = "postgres"` only after these values and the tables are ready. Missing/invalid cloud configuration and database outages stop the app; they never fall back to temporary storage while claiming data is saved.

Do not paste credentials in GitHub issues, commits or chat. For local testing, put them in the ignored `.streamlit/secrets.toml` and use a separately registered local callback `http://localhost:8501/oauth2callback`.

## 4. Restore and verify

1. Sign in with the allowlisted account. Confirm the app says **Private cloud storage connected**.
2. Import your existing complete JSON backup once. Identical re-imports are safe. Android session-only JSON does not change your settings or sleep records.
3. Confirm a saved-through timestamp/revision appears. Reload the page and confirm your records and settings return.
4. Open the app in another browser, sign in with the same account, and confirm the same records appear.
5. A signed-out visitor should see only Sign in. An account outside the allowlist should see no records or forms.

Provider subject + issuer determines ownership; changing your email on the same identity retains the same records after you update the allowlist. Switching to a different provider/account does not silently transfer records. Export/import is the explicit migration path.

## Durability, isolation and recovery

PostgreSQL is the durable source of truth. Each app rerun reads a consistent private snapshot. Each write locks the account row, validates against the latest committed dataset, and commits records/settings together. Concurrent non-overlapping imports merge; overlapping/conflicting imports are rejected. A success message appears only after the commit completes. If the response to a commit is interrupted, reload before repeating manual entry; identical file imports are idempotent.

Authorization happens before opening the database. Queries always use an owner ID derived from verified OIDC claims, not a widget or query parameter. This is server-enforced tenant isolation; the database credential itself can access all Dawnflux tenants and must remain private. It is not end-to-end encryption or protection against the database/server administrator.

There is deliberately no automatic deletion or correction overwrite in this change. Keep periodic JSON backups in addition to provider storage. Check and configure your Neon plan's restore/backup retention separately; this change does not purchase a backup plan or promise unlimited retention. Test restoring a JSON export into a separate account/database before you rely exclusively on hosted storage.

Official references: [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication), [Neon connection pooling](https://neon.com/docs/connect/connection-pooling), [Neon secure connections](https://neon.com/docs/connect/connect-securely).
