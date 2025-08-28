# Supabase configuration for Authentication System

This document describes the Supabase setup (SQL schema, RLS policies, Auth settings) to support:
- Users linked to Supabase Auth (auth.users)
- Email verification and password reset using secure, short-lived codes
- Security policies for least-privileged access
- Minimal edge functions (optional) and recommended settings

Notes:
- Execute the SQL in the order presented.
- For production, use the Supabase Dashboard SQL editor or the CLI.
- Do NOT expose the Service Role key to the frontend. The backend already uses SUPABASE_SERVICE_ROLE_KEY.

ENV variables required by the backend (set via container .env):
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL, SITE_URL

Contents:
1) Schema (applied)
2) Security (RLS policies) (applied)
3) Auth configuration
4) Optional: rate limiting via Postgres
5) Operational guidance
6) What this automation executed

-------------------------------------------------------------------------------
1) SCHEMA
-------------------------------------------------------------------------------

-- Create application schema
create schema if not exists app;

-- 1.1 profiles table: optional profile linked to auth.users
create table if not exists app.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  is_email_verified boolean not null default false
);

-- Keep email in sync with auth.users on insert/update
create or replace function app.set_profile_email()
returns trigger
language plpgsql
security definer
as $$
begin
  if tg_op = 'INSERT' then
    if new.email is null then
      select u.email into new.email from auth.users u where u.id = new.user_id;
    end if;
  elsif tg_op = 'UPDATE' then
    if new.email is distinct from old.email and new.email is null then
      select u.email into new.email from auth.users u where u.id = new.user_id;
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_profiles_set_email on app.profiles;
create trigger trg_profiles_set_email
before insert or update on app.profiles
for each row execute procedure app.set_profile_email();

-- 1.2 verification codes: used for email verification and password reset (code-based)
-- Note: Supabase SQL runner may not support "if not exists" for CREATE TYPE; created explicitly.
create type app.code_purpose as enum ('email_verification', 'password_reset');

create table if not exists app.verification_codes (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  purpose app.code_purpose not null,
  code text not null, -- store as text to allow alphanumeric codes
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint uq_active_code unique (user_id, purpose, code)
);

-- Indexes for quick lookups and expiry cleanup
create index if not exists idx_verification_codes_user_purpose on app.verification_codes(user_id, purpose);
create index if not exists idx_verification_codes_email_purpose on app.verification_codes(email, purpose);
create index if not exists idx_verification_codes_expires on app.verification_codes(expires_at);
create index if not exists idx_verification_codes_consumed on app.verification_codes(consumed_at);

-- 1.3 housekeeping function to auto-expire/cleanup (optional; use cron)
create or replace function app.purge_expired_codes()
returns void
language plpgsql
security definer
as $$
begin
  delete from app.verification_codes
  where (expires_at < now() - interval '1 hour') -- keep 1h history after expiration
     or (consumed_at is not null and consumed_at < now() - interval '1 hour');
end;
$$;

-- 1.4 helper function to mark profile email verified when a verification code is consumed
create or replace function app.mark_email_verified(p_user_id uuid)
returns void
language plpgsql
security definer
as $$
begin
  update app.profiles
  set is_email_verified = true,
      updated_at = now()
  where user_id = p_user_id;
end;
$$;

-------------------------------------------------------------------------------
2) SECURITY (RLS POLICIES)
-------------------------------------------------------------------------------

-- Enable Row Level Security
alter table app.profiles enable row level security;
alter table app.verification_codes enable row level security;

-- Profiles policies:
-- - Users can select their own profile.
-- - Users can insert their profile (first time) for themselves.
-- - Users can update their own profile.
-- No delete by end-users.

-- SELECT
drop policy if exists "Profiles: owner can select" on app.profiles;
create policy "Profiles: owner can select"
on app.profiles for select
to authenticated
using (auth.uid() = user_id);

-- INSERT
drop policy if exists "Profiles: owner can insert" on app.profiles;
create policy "Profiles: owner can insert"
on app.profiles for insert
to authenticated
with check (auth.uid() = user_id);

-- UPDATE
drop policy if exists "Profiles: owner can update" on app.profiles;
create policy "Profiles: owner can update"
on app.profiles for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- Verification codes policies:
-- Typically, application server (service role) manages these.
-- Allow read of own, but not write by client. Inserts/updates/deletes only via service role.

-- SELECT: allow authenticated user to read their own codes (optional; can be removed to harden)
drop policy if exists "Codes: owner can select own" on app.verification_codes;
create policy "Codes: owner can select own"
on app.verification_codes for select
to authenticated
using (auth.uid() = user_id);

-- No INSERT/UPDATE/DELETE policies for authenticated users (only service role can perform via backend).

-------------------------------------------------------------------------------
3) AUTH CONFIGURATION
-------------------------------------------------------------------------------

In Supabase Dashboard -> Authentication -> Providers/Settings:

- Email auth: Enabled
- Email confirmations: Enabled
- Password min length: 8+
- Secure password reset: Enabled
- Site URL: Set to your frontend URL (same as SITE_URL in backend)
- Redirect URLs: Include your frontend verification and password reset pages if applicable

Recommended Auth email templates:
- Confirm signup (email verification): uses magic link; backend also supports sending link with Admin API.
- Reset password: uses recovery link.

If you want to support code-based verification/reset instead of links:
- Use the app.verification_codes table and have the backend generate short-lived codes, email via SMTP, and verify/consume codes on submit.
- The current backend endpoints expose placeholders for code-based flows and already send links. You can extend them later if required.

-------------------------------------------------------------------------------
4) OPTIONAL: RATE LIMITING VIA POSTGRES
-------------------------------------------------------------------------------
For strict per-email send limits, you can implement a table and use RLS or Postgres advisory locks.
However, since the backend already implements a simple in-memory limiter, this is optional.
For multi-instance deployments, prefer Redis or pg-based rate limiting.

-------------------------------------------------------------------------------
5) OPERATIONAL GUIDANCE
-------------------------------------------------------------------------------

- Running the SQL:
  - Already executed by automation via Supabase Admin tools.
  - Verified tables exist in "app" schema: app.profiles, app.verification_codes; enum app.code_purpose created; functions and triggers installed.
  - If you need to re-apply manually, use authentication_backend/assets/supabase_schema.sql in the Supabase SQL Editor.

- Cleaning codes periodically:
  - Set a cron (e.g., daily) to call: select app.purge_expired_codes();
  - Or add a Scheduled Function (Edge function or PG cron extension) if available.

- Access patterns:
  - Frontend should not access app.verification_codes directly.
  - Backend uses the Service Role key for inserts/updates into verification_codes when implementing code-based flows.

- Social logins:
  - Enable providers in Supabase Auth settings as needed.
  - Profiles table will still map by user_id.

-------------------------------------------------------------------------------
6) WHAT THIS AUTOMATION EXECUTED
-------------------------------------------------------------------------------

The following actions were performed against your Supabase instance:

1. Checked existing tables.
2. Created schema: app
3. Created table: app.profiles (with PK referencing auth.users)
4. Created trigger function: app.set_profile_email, and trigger: trg_profiles_set_email
5. Created enum type: app.code_purpose ('email_verification', 'password_reset')
6. Created table: app.verification_codes
7. Created indexes: user_purpose, email_purpose, expires, consumed
8. Created functions: app.purge_expired_codes, app.mark_email_verified
9. Enabled RLS on app.profiles and app.verification_codes
10. Installed RLS policies:
    - Profiles: owner can select/insert/update
    - Codes: owner can select own

Environment variables:
- Backend: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL, SITE_URL
- Frontend: REACT_APP_BACKEND_URL; optional: REACT_APP_SUPABASE_URL, REACT_APP_SUPABASE_ANON_KEY, REACT_APP_SITE_URL

Ensure in Supabase Dashboard -> Authentication -> URL Configuration:
- Site URL set to your frontend URL
- Add redirect URLs:
  - http://localhost:3000/**
  - https://<your-domain>/**

Change log:
- Initial version created by automation.
- Updated after automated execution to reflect applied schema and policies.
