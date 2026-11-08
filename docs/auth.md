# Auth

The app supports three login flows and lets you enable any combination of them
with `AUTH_METHODS`:

| Method | Flow | Endpoints enabled |
| --- | --- | --- |
| `password` | username, email or phone plus a password | `/api/auth/signup`, `/api/auth/login` |
| `email_otp` | passwordless code sent to an email address | `/api/auth/otp/request`, `/api/auth/otp/login` |
| `phone_otp` | passwordless code sent to a phone number | `/api/auth/otp/request`, `/api/auth/otp/login` |

`AUTH_METHODS` defaults to `password,email_otp,phone_otp`. Unknown names are
ignored. A disabled flow answers:

```json
{"errcode": "AuthMethodDisabled", "detail": "auth method is disabled"}
```

with status `404`. For the OTP endpoints the check is per identifier: an email
request needs `email_otp`, a phone request needs `phone_otp`.

## Validation

Request models live in `features/users/model.py`:

- `username`: 3 to 127 characters, `[A-Za-z0-9_.-]+`
- `email`: up to 511 characters, basic `name@host.tld` pattern
- `phone_number`: optional `+`, then 7 to 31 digits
- `password`: 8 to 128 characters on signup, 1 to 128 on login
- `code`: exactly six digits
- OTP requests and logins strip surrounding whitespace

Failing validation returns the FastAPI default `422 {"detail": [...]}`, not the
error envelope.

## Endpoints

Everything under `/api/auth/` is public. Other `/api/*` routes require
`Authorization: Bearer <token>`.

### POST /api/auth/signup

At least one identity field plus a password.

```json
{
  "username": "ada",
  "email": "ada@example.com",
  "phone_number": "100",
  "password": "correct horse battery staple"
}
```

Returns `201` with `{"detail": "ok", "data": {"id": 1}}`. The account role is
always `user`; there is no signup route for other roles. A duplicate username,
email or phone returns `409 UserAlreadyExists`.

### POST /api/auth/login

Exactly one identifier plus the password.

```json
{"username": "ada", "password": "correct horse battery staple"}
```

`email` or `phone_number` may be used instead of `username`. Returns
`{"detail": "ok", "data": {"token": "<jwt>"}}`. A wrong identifier or password
returns `401 InvalidCredentials`.

### POST /api/auth/otp/request

Exactly one of `email` or `phone_number`.

```json
{"email": "ada@example.com"}
```

Always answers `200 {"detail": "ok", "data": {"sent": true}}`, whether or not
the account exists, so the endpoint cannot be used to enumerate users.

When `AUTH_OTP_AUTO_SIGNUP=true` (the default) an unknown identifier creates a
bare user on the first request. When it is `false`, an unknown identifier still
gets the same `sent: true` response but no code is stored or sent.

Codes are six digits and stay valid for `OTP_TTL_MINUTES` (default 5).

### POST /api/auth/otp/login

The same identifier plus the code.

```json
{"email": "ada@example.com", "code": "042913"}
```

Returns a JWT. The code is rejected when it is missing, expired, or does not
match, and is cleared after a successful login.

### GET /api/users/me

Requires a bearer token. Returns `id_`, `username`, `phone_number`, `email`,
`role` and `created_at`. A user that was disabled or soft deleted since the
token was issued returns `404 UserNotFound`.

### GET /api/users

Requires a bearer token whose `role` claim is `admin`. Returns active users with
the same fields plus `isdisabled`. Without the admin role it returns
`403 AdminRequired`.

## Middleware

`middleware/auth.py` wraps the ASGI app and only checks paths equal to `/api` or
starting with `/api/`. The following bypass the check:

- `/`
- `/openapi.json`
- `/docs`
- `/redoc`
- `/docs/oauth2-redirect`
- every path under `/api/auth/`
- any `OPTIONS` request

A request to a protected path must carry a parsable `Authorization: Bearer`
header. Missing, malformed or expired tokens return `401 InvalidToken`. A valid
token has its claims stored on `request.state.user` for the handler. A missing
`APP_SECRET` returns `500 ServerMisconfigured`.

## Errors

Failures use `{"errcode": "<label>", "detail": "<message>"}`. The labels are
`HttpError` objects in `errors.py` and are passed to `StandardResponse` as
objects, so a typo fails at import time instead of silently turning into a 500.
`StandardResponse` also refuses plain strings on the error path.

| Label | Status | Used for |
| --- | --- | --- |
| `AuthMethodDisabled` | 404 | flow disabled by `AUTH_METHODS` |
| `InvalidCredentials` | 401 | wrong username, email, phone or password |
| `InvalidOtp` | 401 | wrong or expired code |
| `InvalidToken` | 401 | missing, malformed or expired bearer token |
| `UserAlreadyExists` | 409 | duplicate username, email or phone number |
| `AdminRequired` | 403 | `/api/users` called without the admin role |
| `UserNotFound` | 404 | `/api/users/me` for a user that is gone or disabled |
| `ServerMisconfigured` | 500 | `APP_SECRET` is not set |

`errors.py` also defines generic codes such as `BadRequest`, `Conflict` and
`TechnicalIssue`. No current route uses them.

## Tokens

JWTs are signed with `HS256` using `APP_SECRET`. The payload is
`{"user_id": <int>, "role": "<role>", "exp": <expiry>}` and the lifetime is
`ACCESS_TOKEN_TTL_HOURS` (default 24).

Tokens are stateless. There is no revocation list, so logout is client side, and
a role change in the database does not affect an already issued token until it
expires. `/api/users` authorizes from the token's `role` claim, not from a fresh
database read.

## Local development

`APP_ENV=dev` (the default) makes the OTP senders log the code with structlog.
Outside development they only warn that delivery is not configured.

```bash
# password flow
curl -X POST localhost:8000/api/auth/signup \
  -H 'content-type: application/json' \
  -d '{"username":"ada","email":"ada@example.com","password":"password123"}'

curl -X POST localhost:8000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"ada","password":"password123"}'

# email OTP flow
curl -X POST localhost:8000/api/auth/otp/request \
  -H 'content-type: application/json' \
  -d '{"email":"ada@example.com"}'

curl -X POST localhost:8000/api/auth/otp/login \
  -H 'content-type: application/json' \
  -d '{"email":"ada@example.com","code":"042913"}'
```

Signup returns an id, not a token, so run login (or OTP login) before calling
the protected routes.

## Security notes

- `lib/otp/email.py` and `lib/otp/phone.py` are placeholders. They log the code
  in development and warn outside it. Wire a real provider before deploying.
- No rate limiting is included. Add it at the reverse proxy or in the OTP
  request handler before going to production.
- OTPs are stored in plain text, compared with `secrets.compare_digest`, and
  cleared after use. Hash them in the database if your threat model requires it.
- Passwords use argon2id through `lib/hash.py`.
- Password login runs a dummy argon2 verification when the account is missing,
  so response time does not reveal whether a user exists.
- There is no CORS middleware. Add one if a browser app on another origin calls
  the API directly.
