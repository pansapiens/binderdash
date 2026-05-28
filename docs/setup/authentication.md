# Authentication Setup

Binderdash supports five authentication modes:

- Auth disabled (public API)
- Session auth via local bcrypt users
- Session auth via PAM (Unix accounts)
- Session auth via Google OAuth (OIDC)
- Static API key auth for scripted access

You can enable multiple auth providers at the same time. The sections below describe how to configure each mode and how precedence works when multiple are enabled.

## Quick Reference

- `DISABLE_AUTHENTICATION="true"` makes all protected endpoints public and bypasses provider checks.
- Session auth uses cookies (`binderdash_session`) and CSRF protection for non-GET requests.
- API key auth uses either `Authorization: Bearer <key>` or `X-Binderdash-Api-Key: <key>`.
- Username/password login (`POST /api/auth/login`) checks local users first, then PAM (if enabled).
- Google OAuth signs in through `/api/auth/google/login` and creates the same session cookies as local/PAM login.

## Environment Variables

These are the auth-related variables currently supported in `.env.example`:

- `DISABLE_AUTHENTICATION`
- `BINDERDASH_API_KEY`
- `LOCAL_USERS`
- `PAM_LOCAL_ENABLED`
- `PAM_LOCAL_ALLOWED_USERS`
- `PAM_LOCAL_SERVICE`
- `GOOGLE_AUTH_ENABLED`
- `GOOGLE_AUTH_CLIENT_ID`
- `GOOGLE_AUTH_CLIENT_SECRET`
- `GOOGLE_AUTH_REDIRECT_URI`
- `GOOGLE_AUTH_ALLOWED_USERS`
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`

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

## Auth Type 5: Static API Key

Use this for scripts/agents without browser session or CSRF handling.

```bash
BINDERDASH_API_KEY="your-long-random-secret"
DISABLE_AUTHENTICATION="false"
```

Use either header format:

```http
Authorization: Bearer your-long-random-secret
```

or

```http
X-Binderdash-Api-Key: your-long-random-secret
```

Notes:

- For state-changing requests, API key auth bypasses CSRF checks.
- On protected routes, a valid API key is accepted before cookie auth.
- `/api/auth/me` requires cookie session auth (it does not accept API key auth).

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
  "providers": {
    "local": { "enabled": true },
    "pam": { "enabled": false },
    "google": { "enabled": true, "login_url": "/api/auth/google/login" },
    "api_key": { "enabled": true }
  }
}
```

## Recommended Combinations

- **Local dev (public)**: `DISABLE_AUTHENTICATION="true"`
- **Team dev (session login)**: local users and/or PAM, `DISABLE_AUTHENTICATION="false"`
- **Production user login**: Google OAuth + allowlist, `DISABLE_AUTHENTICATION="false"`
- **Automation access**: set `BINDERDASH_API_KEY` (can coexist with any session provider)
