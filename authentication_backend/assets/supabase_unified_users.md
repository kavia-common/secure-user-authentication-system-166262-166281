# Supabase unified users schema

This document describes the migration from the legacy tables (app.profiles and app.verification_codes) to a single unified table public.users that supports all core flows: signup, email verification (6-digit code), and password reset code.

What changes
- Drops:
  - app.profiles
  - app.verification_codes
  - app.code_purpose enum
- Creates:
  - public.users with fields:
    - id (uuid, PK)
    - email (unique)
    - hashed_password
    - is_email_verified
    - current_verification_code
    - code_expires_at
    - code_attempts
    - password_reset_code
    - password_reset_expires
    - created_at
    - updated_at
- Adds:
  - updated_at trigger
  - helpful indexes
  - basic RLS policies (owner can select/update self). The backend continues to use the Service Role and is not limited by RLS.

Why public schema?
- The public schema is the most visible and easiest to work with from Supabase Dashboard.
- You can still add RLS policies to restrict client access; the backend uses the Service Role and bypasses RLS.

How to apply
1) Open Supabase Dashboard -> SQL editor.
2) Paste and run the contents of authentication_backend/assets/supabase_users_unified.sql
3) Verify public.users is created and old tables are removed.

Backend integration notes
- The backend should switch from writing to app.verification_codes/app.profiles to using fields in public.users:
  - On signup:
    - Create a row with email, hashed_password, is_email_verified=false.
    - Generate a 6-digit current_verification_code and set code_expires_at.
  - On verify:
    - Check current_verification_code and code_expires_at.
    - If valid, set is_email_verified=true and clear current_verification_code/code_expires_at/code_attempts.
  - On forgot password:
    - Generate password_reset_code and password_reset_expires.
  - On reset password:
    - Validate password_reset_code/password_reset_expires, update hashed_password, then clear reset fields.

Security guidance
- Keep RLS enabled on public.users.
- Only authenticated users can select/update their own record if you expose PostgREST directly to the client.
- In server operations, use the Service Role key as already configured in the backend; SRK bypasses RLS.
- Do NOT store plaintext passwords; use strong hashing (argon2/bcrypt) strictly on the server.

Operational notes
- If you need a link to auth.users, you can extend the table:
  - auth_user_id uuid unique references auth.users(id) on delete cascade
- If you use Supabase Auth for session issuance, you can continue to do so.
- Remove any code that depended on app.profiles/app.verification_codes DAO and replace with simple read/write into public.users.

Rollback
- If needed, you can recreate the prior schema from authentication_backend/assets/supabase_schema.sql (legacy).
