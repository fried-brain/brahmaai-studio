# Authentication API

Base path: `/api/v1`

## `POST /auth/register`

Request JSON: `email`, `password` (minimum 12 characters), optional `display_name`.

Returns `201` with the public user profile. Password hashes are never returned. Duplicate email returns `409`; invalid input returns `422`.

## `POST /auth/login`

Request JSON: `email`, `password`.

Returns the public user profile and `csrf_token`; sets the `bas_session` HttpOnly cookie. Invalid credentials return `401`.

## `GET /auth/me`

Requires the session cookie. Returns the public user profile or `401`.

## `POST /auth/logout`

Requires the session cookie and `X-CSRF-Token` header. Revokes the server-side session and clears the cookie. Missing/invalid CSRF token returns `403`.

## `GET /health`

Reports application and database connectivity. A configured but unreachable database returns `503`.
