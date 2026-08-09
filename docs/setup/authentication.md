# Authentication Setup

Binderdash supports five authentication modes:

- Auth disabled (public API)
- Session auth via local bcrypt users
- Session auth via PAM (Unix accounts)
- Session auth via Google OAuth (OIDC)
- Per-user API key auth for scripted access

You can enable multiple auth providers at the same time. The sections below describe how to configure each mode and how precedence works when multiple are enabled.

## Quick Reference

- `DISABLE_AUTHENTICATION="true"` makes all protected endpoints public and bypasses provider checks.
- Session auth uses cookies (`binderdash_session`) and CSRF protection for non-GET requests.
- API key auth uses either `Authorization: Bearer <key>` or `X-Binderdash-Api-Key: <key>`. Keys are per-user, named, expiring, and revocable — there is no single shared server secret — and require `DATABASE` to be configured.
- Username/password login (`POST /api/auth/login`) checks local users first, then PAM (if enabled).
- Google OAuth signs in through `/api/auth/google/login` and creates the same session cookies as local/PAM login.
- Every successful login resolves to a **user** (see "User model and admin allowlist" below); `BINDERDASH_ADMIN_USERS` is re-applied on every startup and login.

## Environment Variables

These are the auth-related variables currently supported in `.env.example`:

- `DISABLE_AUTHENTICATION`
- `LOCAL_USERS`
- `PAM_LOCAL_ENABLED`
- `PAM_LOCAL_ALLOWED_USERS`
- `PAM_LOCAL_SERVICE`
- `PAM_GECOS_EMAIL`
- `GOOGLE_AUTH_ENABLED`
- `GOOGLE_AUTH_CLIENT_ID`
- `GOOGLE_AUTH_CLIENT_SECRET`
- `GOOGLE_AUTH_REDIRECT_URI`
- `GOOGLE_AUTH_ALLOWED_USERS`
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `BINDERDASH_ADMIN_USERS`
- `DATABASE` (required for per-user API keys to exist at all)

## Provider Precedence and Coexistence

When multiple options are enabled, behaviour is:

1. **Global override**: if `DISABLE_AUTHENTICATION="true"`, auth is bypassed for protected routes.
2. **Protected API route auth** (when auth is enabled):
   - API key is checked first.
   - If no valid API key, session cookie auth is checked.
3. **Username/password login flow** (`POST /api/auth/login`):
   - Local bcrypt users are checked first.
   - PAM is checked only if local auth did not match and `PAM_LOCAL_ENABLED="true"`.
4. **Google OAuth flow**:
   - Independent login path; if successful, issues session cookies.
   - Then protected routes use normal cookie/API-key precedence above.

## Auth Type 1: Disable Authentication (Public Mode)

Use this for local development only.

```bash
DISABLE_AUTHENTICATION="true"
```

Notes:

- Protected endpoints no longer require login, API key, or CSRF.
- You can leave other auth variables set; they are effectively bypassed while this is `true`.

## Auth Type 2: Local Username/Password (bcrypt)

Enable local session login with bcrypt hashes in `LOCAL_USERS`.

### Step 1: Generate bcrypt hashes

```bash
python backend/scripts/encrypt_password.py alice
python backend/scripts/encrypt_password.py bob
```

### Step 2: Set `LOCAL_USERS`

```bash
LOCAL_USERS="alice:$2b$12$...,bob:$2b$12$..."
DISABLE_AUTHENTICATION="false"
```

### Step 3: Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "alice",
  "password": "your-password"
}
```

Successful login returns user details plus `csrf_token`, and sets session cookies.

## Auth Type 3: PAM Username/Password (Unix Accounts)

Enable PAM-based login for allowed system users.

```bash
PAM_LOCAL_ENABLED="true"
PAM_LOCAL_ALLOWED_USERS="ubuntu,bob,alice"   # comma-separated list, or "*" for any PAM-valid user
PAM_LOCAL_SERVICE="common-auth"
DISABLE_AUTHENTICATION="false"
```

Important:

- PAM login is attempted only after local user auth fails.
- `PAM_LOCAL_ALLOWED_USERS` is required in practice (`*` or a comma-separated allowlist; case-insensitive).
- In containers, host users usually do not exist unless explicitly provided.

### PAM with Docker Compose (required host account binds)

When Binderdash runs in Docker, PAM checks the container's user database by default.  
That usually includes only container users (for example `app`), not host users like `perry`.

To authenticate host Linux users through PAM in Docker, you must bind host account files read-only:

```yaml
services:
  binderdash:
    volumes:
      - /etc/passwd:/etc/passwd:ro
      - /etc/group:/etc/group:ro
      - /etc/shadow:/etc/shadow:ro
```

This is already shown as commented examples in `docker-compose.dev.yml`; uncomment them to enable host-user PAM login.

Recommended matching env:

```bash
PAM_LOCAL_ENABLED="true"
PAM_LOCAL_ALLOWED_USERS="bob,alice"   # comma-separated list, or "*" for broader access
PAM_LOCAL_SERVICE="common-auth"
DISABLE_AUTHENTICATION="false"
```

After changing compose mounts or env values, recreate the container so PAM sees the updated runtime:

```bash
docker compose up -d --build
```

Security note:

- Mounting `/etc/shadow` into a container exposes password-hash data to that container.
- Use this only on trusted development hosts, with minimal container access.
- For safer container auth in many cases, prefer `LOCAL_USERS` (bcrypt) instead of PAM.

## Auth Type 4: Google OAuth (OIDC)

Enable Google sign-in and restrict it to allowed emails.

### Step 1: Configure Google credentials

```bash
GOOGLE_AUTH_ENABLED="true"
GOOGLE_AUTH_CLIENT_ID="..."
GOOGLE_AUTH_CLIENT_SECRET="..."
GOOGLE_AUTH_REDIRECT_URI="http://localhost:8000/api/auth/google/callback"
GOOGLE_AUTH_ALLOWED_USERS="user1@example.com,user2@example.com"
DISABLE_AUTHENTICATION="false"
```

### Step 2: Configure redirect URI in Google Cloud

Your Google OAuth client must include the same callback URI as `GOOGLE_AUTH_REDIRECT_URI`.

### Step 3: Start login flow

Open:

```text
/api/auth/google/login
```

Notes:

- Google auth is considered configured only when enabled and client ID/secret/redirect URI are all non-empty.
- If `GOOGLE_AUTH_ALLOWED_USERS` is empty, Google sign-in is effectively denied for everyone.
- Successful callback issues the same session cookies as local/PAM login.

## Auth Type 5: Per-User API Key

Use this for scripts/agents without browser session or CSRF handling.

Unlike the other four modes, this isn't a server-wide toggle — it's a capability of the user model, gated on persistence:

```bash
DATABASE="sqlite:///./binderdash.db"   # or Postgres URL; keys live in the DB
DISABLE_AUTHENTICATION="false"
```

Create a user and a key for them, either via the web UI (account menu, top-right → "API keys") or the CLI:

```bash
python -m backend.cli user create --email you@example.org --admin
python -m backend.cli key create you@example.org --name bootstrap
```

The token prints to stdout alone (a warning goes to stderr) and is shown **once** — the server stores only a SHA-256 hash. Other CLI subcommands: `user list|show|link-identity|set-admin`, `key list|revoke`.

Use either header format:

```http
Authorization: Bearer <token>
```

or

```http
X-Binderdash-Api-Key: <token>
```

Notes:

- For state-changing requests, API key auth bypasses CSRF checks.
- On protected routes, a valid API key is accepted before cookie auth.
- `/api/auth/me` requires cookie session auth (it does not accept API key auth).
- Keys are named, can have an expiry (`--expires-days`), and are individually revocable (`key revoke <id>`); revocation takes effect immediately.
- With no `DATABASE` configured, `GET /api/auth/status` reports `api_keys.enabled: false, reason: "persistence_disabled"` and the key-management endpoints return `503`.
- **Key management is session-only.** `GET/POST /api/api-keys` and `PATCH/DELETE /api/api-keys/{id}` reject API-key-authenticated requests with `403` — a leaked key must not be able to mint its own replacement or see other keys. `GET /api/users` is additionally admin-only.

## User model and admin allowlist

A **user** is a person. An **identity** is one login method, keyed on `(provider, identifier)` — e.g. `local:alice`, `pam:alice`, `google:alice@example.org`. A user is auto-created on first successful login. Two identities are merged onto the same user only when they share a **verified email** (so, for example, PAM login for `alice` and Google login for `alice@example.org` merge only if `PAM_GECOS_EMAIL` resolves the same address — see below — otherwise they stay separate users).

`BINDERDASH_ADMIN_USERS` is a comma-separated allowlist granting `is_admin`. Each entry matches against a login's email, its `provider:identifier` pair, or a bare username/identifier — there is deliberately **no `*` wildcard** (unlike `PAM_LOCAL_ALLOWED_USERS`, "everyone is an admin" should never be a one-character mistake). The allowlist is re-applied at every startup and at every login, so revoking admin access just means removing the entry and waiting for the next login (or restart) — `is_admin` set only via `python -m backend.cli user set-admin` will not stick if the user isn't also in `BINDERDASH_ADMIN_USERS`.

### `PAM_GECOS_EMAIL`

Default `false`. When `true`, PAM login resolves the user's email from the **5th GECOS field only** ("other"), never fields 1–4 ("full name", "room", "work phone", "home phone").

This is a security boundary, not a formatting preference: `chfn` lets ordinary users rewrite their own GECOS, and `/etc/login.defs`'s `CHFN_RESTRICT` commonly ships as `"rwh"` — meaning room, work phone, and home phone are user-writable, but there is no `chfn` flag for the 5th field, so only root can set it (and `chfn` rejects commas in input, so a user can't smuggle extra fields in). Trusting an earlier, user-writable field would let any shell user run `chfn` to claim a colleague's email address and get merged into their Binderdash account — inheriting their API keys and admin rights.

## Session and CSRF Behaviour

When auth is enabled and you use session cookies:

- Server sets:
  - `binderdash_session` (HttpOnly session token)
  - `binderdash_csrf` (readable cookie)
- For non-GET/HEAD/OPTIONS requests, send `X-CSRF-Token` matching `binderdash_csrf`.

CSRF checks are skipped for:

- `/api/auth/login`
- `/api/auth/logout`
- `/api/auth/status`
- `/api/auth/google/login`
- `/api/auth/google/callback`
- Any request with a valid API key

## Verify Active Providers

Use:

```http
GET /api/auth/status
```

Response shape:

```json
{
  "auth_disabled": false,
  "desktop_mode": false,
  "providers": {
    "local": { "enabled": true },
    "pam": { "enabled": false },
    "google": { "enabled": true, "login_url": "/api/auth/google/login" }
  },
  "api_keys": { "enabled": true, "reason": null }
}
```

`api_keys.reason` is `null` when keys are usable, `"auth_disabled"` when `DISABLE_AUTHENTICATION=true` (there is nothing to scope a key to), or `"persistence_disabled"` when no `DATABASE` is configured.

## Recommended Combinations

- **Local dev (public)**: `DISABLE_AUTHENTICATION="true"`
- **Team dev (session login)**: local users and/or PAM, `DISABLE_AUTHENTICATION="false"`
- **Production user login**: Google OAuth + allowlist, `DISABLE_AUTHENTICATION="false"`
- **Automation access**: configure `DATABASE`, then mint per-user keys via the UI or `python -m backend.cli key create` (coexists with any session provider)
