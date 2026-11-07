# Auth

The template supports three login flows and lets you enable any combination of
them with `AUTH_METHODS`:

| Method      | Flow                                        | Endpoints enabled                |
| ----------- | ------------------------------------------- | -------------------------------- |
| `password`  | username, email or phone + password         | `/api/auth/signup`, `/api/auth/login` |
| `email_otp` | passwordless code sent to an email address  | `/api/auth/otp/request`, `/api/auth/otp/login` |
| `phone_otp` | passwordless code sent to a phone number    | `/api/auth/otp/request`, `/api/auth/otp/login` |

`AUTH_METHODS` defaults to `password,email_otp,phone_otp`. A disabled flow
answers `404 {"errcode": "AuthMethodDisabled", "detail": "auth method is disabled"}`.

## Endpoints

Everything under `/api/auth/` is public. Other `/api/*` routes require
`Authorization: Bearer <token>`.

### POST /api/auth/signup

At least one identity field plus a password of 8 or more characters.

```json
{
  "username": "ada",
  "email": "ada@example.com",
  "phone_number": "100",
  "password": "correct horse battery staple"
}
```

Returns `201` with `{"detail": "ok", "data": {"id": 1}}`. A duplicate username,
email or phone returns `409`.

### POST /api/auth/login

Exactly one identifier plus the password.

```json
{"username": "ada", "password": "correct horse battery staple"}
```

`email` or `phone_number` can be used instead of `username`. Returns
`{"detail": "ok", "data": {"token": "<jwt>"}}`.

### POST /api/auth/otp/request

Exactly one of `email` or `phone_number`.

```json
{"email": "ada@example.com"}
```

Always returns `{"detail": "ok", "data": {"sent": true}}`, whether or not the
account exists, so the endpoint cannot be used to enumerate users. When
`AUTH_OTP_AUTO_SIGNUP=true` (the default) an unknown identifier creates a bare
user on first request.

### POST /api/auth/otp/login

The same identifier plus the six digit code.

```json
{"email": "ada@example.com", "code": "042913"}
```

Returns a JWT. The OTP is cleared after a successful login, and the code is
rejected once `OTP_TTL_MINUTES` has passed.

### GET /api/users/me

Requires a bearer token. Returns `id_`, `username`, `phone_number`, `email`,
`role` and `created_at`. Sensitive columns are never part of the response
model.

### GET /api/users

Requires a bearer token whose `role` claim is `admin`. Returns active users
with the same fields plus `isdisabled`.

## Errors

Failures use `{"errcode": "<label>", "detail": "<message>"}`. The codes live in
`errors.py` and are passed to `StandardResponse` as objects, so a typo fails at
import time instead of silently turning into a 500.

| Label                | Status | Used for                                            |
| -------------------- | ------ | --------------------------------------------------- |
| `AuthMethodDisabled` | 404    | flow disabled by `AUTH_METHODS`                     |
| `InvalidCredentials` | 401    | wrong username, email, phone or password            |
| `InvalidOtp`         | 401    | wrong or expired code                               |
| `InvalidToken`       | 401    | missing, malformed or expired bearer token          |
| `UserAlreadyExists`  | 409    | duplicate username, email or phone number           |
| `AdminRequired`      | 403    | `/api/users` called without the admin role          |
| `UserNotFound`       | 404    | `/api/users/me` for a user that no longer exists    |
| `ServerMisconfigured`| 500    | `APP_SECRET` is not set                             |

## Tokens

JWTs are signed with `HS256` using `APP_SECRET`, which is required. The payload
is `{"user_id": <int>, "role": "<role>", "exp": <expiry>}` and the default
lifetime is `ACCESS_TOKEN_TTL_HOURS=24`. Tokens are stateless: there is no
revocation list, so log out is client side.

## Local development

`APP_ENV=dev` (the default) makes the OTP senders log the code with structlog.
Outside dev they only warn that delivery is not configured.

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

## Security notes

- `lib/otp/email.py` and `lib/otp/phone.py` are placeholders that log. Wire a
  real provider before deploying.
- No rate limiting is included. Add it at the reverse proxy or in the OTP
  request handler before going to production.
- OTPs are stored in plain text and cleared after use. Hash them in the database
  if your threat model requires it.
- Bcrypt/argon2 password hashing is argon2id via `lib/hash.py`.
- Password login runs a dummy hash when the account is missing, so response
  time does not reveal whether a user exists.
