-- name: GetUser :one
SELECT id, username, phone_number, email, role, created_at
FROM users
WHERE id = @user_id
    AND isdisabled = false
    AND deleted_at IS NULL;


-- name: ListUsers :many
SELECT id, username, phone_number, email, role, created_at, isdisabled
FROM users
WHERE isdisabled = false
    AND deleted_at IS NULL
ORDER BY username NULLS LAST;


-- name: GetUserByUsername :one
SELECT id, username, phone_number, email, password_hash, role, isdisabled, deleted_at
FROM users
WHERE username = @username
    AND isdisabled = false
    AND deleted_at IS NULL;


-- name: GetUserByEmail :one
SELECT id, username, phone_number, email, password_hash, role, isdisabled, deleted_at, otp, otp_expires_at
FROM users
WHERE email = @email
    AND isdisabled = false
    AND deleted_at IS NULL;


-- name: GetUserByPhoneNumber :one
SELECT id, username, phone_number, email, password_hash, role, isdisabled, deleted_at, otp, otp_expires_at
FROM users
WHERE phone_number = @phone_number
    AND isdisabled = false
    AND deleted_at IS NULL;


-- name: CreateUser :one
INSERT INTO users (username, phone_number, email, password_hash, role)
VALUES (
    @username,
    @phone_number,
    @email,
    @password_hash,
    @role
)
RETURNING id;


-- name: SetOtpByEmail :exec
UPDATE users
SET otp = @otp_code, otp_expires_at = @otp_expires_at, updated_at = now()
WHERE email = @email
    AND isdisabled = false
    AND deleted_at IS NULL;


-- name: SetOtpByPhoneNumber :exec
UPDATE users
SET otp = @otp_code, otp_expires_at = @otp_expires_at, updated_at = now()
WHERE phone_number = @phone_number
    AND isdisabled = false
    AND deleted_at IS NULL;


-- name: ClearOtpByEmail :exec
UPDATE users
SET otp = NULL, otp_expires_at = NULL, updated_at = now()
WHERE email = @email
    AND isdisabled = false
    AND deleted_at IS NULL;


-- name: ClearOtpByPhoneNumber :exec
UPDATE users
SET otp = NULL, otp_expires_at = NULL, updated_at = now()
WHERE phone_number = @phone_number
    AND isdisabled = false
    AND deleted_at IS NULL;
