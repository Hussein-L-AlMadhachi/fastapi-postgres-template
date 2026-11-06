-- name: GetUser :one
SELECT id, email, created_at
FROM users
WHERE id = @user_id;



-- name: ListUsers :many
SELECT id, username, phone_number, email, created_at, isdisabled
FROM users
where isdisabled <> false
    AND isdisabled
    AND deleted_at IS NOT NULL
ORDER BY username;



-- name: GetUserByUsername :one
SELECT id, username, phone_number, email, password_hash, isdisabled, deleted_at
FROM users
WHERE username = @username
    AND isdisabled
    AND deleted_at IS NOT NULL;



-- name: GetUserByEmail :one
SELECT id, username, phone_number, email, otp, otp_expires_at
FROM users
WHERE email = @email
    AND isdisabled
    AND deleted_at IS NOT NULL;



-- name: GetUserByPhoneNumber :one
SELECT id, username, phone_number, email, otp, otp_expires_at
FROM users
WHERE phone_number = @phone_number
    AND isdisabled
    AND deleted_at IS NOT NULL;



-- name: CreateUser :one
INSERT INTO users (id, username, phone_number, email, password_hash)
VALUES (
    @id,
    @username,
    @phone_number,
    @email,
    @password_hash
)
RETURNING id;



-- name: SetOtpByEmail :exec
UPDATE users
SET otp = @otp_code, otp_expires_at = @otp_expires_at
WHERE email = @email
    AND isdisabled
    AND deleted_at IS NOT NULL;



-- name: SetOtpByPhoneNumber :exec
UPDATE users
SET otp = @otp_code, otp_expires_at = @otp_expires_at
WHERE phone_number = @phone_number
    AND isdisabled
    AND deleted_at IS NOT NULL;
