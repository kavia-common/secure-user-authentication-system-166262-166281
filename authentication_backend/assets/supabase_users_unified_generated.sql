-- Unified Users Table Migration (Generated)
-- Purpose:
-- - Drop legacy tables (app.profiles, app.verification_codes) and related enum
-- - Create a unified users table in public schema to store all authentication-related state
-- - Include comments, indexes, triggers, and RLS placeholders
--
-- How to apply:
-- - Open Supabase Dashboard -> SQL editor
-- - Paste and run this script
-- - Verify public.users exists and legacy app.* objects are removed (or ignored if they didn't exist)
--
-- Notes:
-- - This "public.users" is application-managed and separate from auth.users (Supabase's internal user store)
-- - You can optionally add a foreign key to auth.users(id) if you wish to keep linkage
-- - RLS is enabled and basic "owner can read/update self" policies are provided as placeholders
--   (Backends using the Service Role key bypass RLS. Remove or tighten as needed.)
-- - Uses gen_random_uuid(); ensure pgcrypto extension is enabled by default in Supabase.
--   If not, run: create extension if not exists pgcrypto;

begin;

-- 0) Ensure public schema exists (normally present in Supabase)
create schema if not exists public;

-- 1) Drop legacy objects if they exist
do $$
begin
  -- Drop legacy codes table
  if exists (select from information_schema.tables where table_schema = 'app' and table_name = 'verification_codes') then
    execute 'drop table if exists app.verification_codes cascade';
  end if;

  -- Drop legacy profiles table
  if exists (select from information_schema.tables where table_schema = 'app' and table_name = 'profiles') then
    execute 'drop table if exists app.profiles cascade';
  end if;

  -- Drop legacy enum
  if exists (
    select 1
    from pg_type t
    join pg_namespace n on n.oid = t.typnamespace
    where n.nspname = 'app' and t.typname = 'code_purpose'
  ) then
    execute 'drop type app.code_purpose';
  end if;

  -- Optionally drop app schema if now empty (safe guard: only if no tables remain)
  if exists (select 1 from information_schema.schemata where schema_name = 'app') then
    if not exists (select 1 from information_schema.tables where table_schema = 'app') then
      execute 'drop schema app';
    end if;
  end if;
end $$;

-- 2) Create unified users table (application-managed; not the same as auth.users)
create table if not exists public.users (
  -- Core identity
  id uuid primary key default gen_random_uuid(),          -- application-level user ID
  email text not null unique,                             -- unique email for login
  hashed_password text not null,                          -- bcrypt/argon hash (never store plaintext)

  -- Email verification state
  is_email_verified boolean not null default false,       -- set after successful verification
  current_verification_code text,                         -- most recently issued code (nullable)
  code_expires_at timestamptz,                            -- expiry time for the above code (nullable)
  code_attempts int not null default 0,                   -- optional throttle for attempts

  -- Password reset state
  password_reset_code text,                               -- reset code (nullable)
  password_reset_expires timestamptz,                     -- expiry for reset code (nullable)

  -- Operational and audit fields
  last_login timestamptz,                                 -- last successful login (nullable)
  disabled boolean not null default false,                -- disable account without deleting (soft lock)
  created_at timestamptz not null default now(),          -- creation timestamp
  updated_at timestamptz not null default now()           -- auto-updated on change (trigger below)
);

comment on table public.users is
'Application-managed unified users table (separate from auth.users). Stores email, password hash, verification/reset codes, and audit fields.';

comment on column public.users.email is 'Unique email used for login.';
comment on column public.users.hashed_password is 'Password hash (argon2/bcrypt). Never store plaintext.';
comment on column public.users.is_email_verified is 'True once email ownership has been verified.';
comment on column public.users.current_verification_code is 'Latest issued email verification code.';
comment on column public.users.code_expires_at is 'Verification code expiry timestamp.';
comment on column public.users.code_attempts is 'Number of consecutive verify attempts (for rate limiting).';
comment on column public.users.password_reset_code is 'Code used for password reset.';
comment on column public.users.password_reset_expires is 'Password reset code expiry timestamp.';
comment on column public.users.last_login is 'Timestamp of the most recent successful login.';
comment on column public.users.disabled is 'If true, account is locked/disabled.';
comment on column public.users.created_at is 'Creation timestamp.';
comment on column public.users.updated_at is 'Last updated timestamp (maintained by trigger).';

-- 3) Trigger to maintain updated_at
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $fn$
begin
  new.updated_at = now();
  return new;
end;
$fn$;

drop trigger if exists trg_users_set_updated_at on public.users;
create trigger trg_users_set_updated_at
before update on public.users
for each row execute procedure public.set_updated_at();

-- 4) Helpful indexes
-- email lookups in a case-insensitive way
create index if not exists idx_users_email_lower on public.users (lower(email));
-- code expiry checks
create index if not exists idx_users_verification_expiry on public.users (code_expires_at);
create index if not exists idx_users_reset_expiry on public.users (password_reset_expires);
-- last_login queries
create index if not exists idx_users_last_login on public.users (last_login);

-- 5) Optional linkage to auth.users (uncomment if needed)
-- alter table public.users
--   add column if not exists auth_user_id uuid unique references auth.users(id) on delete cascade;

-- 6) RLS (Row Level Security) - placeholders suitable for Supabase
-- Enable RLS so that by default no anonymous access is permitted.
alter table public.users enable row level security;

-- Drop pre-existing policies if re-running
drop policy if exists "Users: owner can select self" on public.users;
drop policy if exists "Users: owner can update self-safe" on public.users;

-- Policy: allow authenticated users to select their own row
create policy "Users: owner can select self"
on public.users for select
to authenticated
using (auth.email() is not null and lower(email) = lower(auth.email()));

-- Policy: allow authenticated users to update their own row (safe subset via PostgREST)
-- Note: Consider restricting client updatable columns further via separate views if exposing directly.
create policy "Users: owner can update self-safe"
on public.users for update
to authenticated
using (auth.email() is not null and lower(email) = lower(auth.email()))
with check (auth.email() is not null and lower(email) = lower(auth.email()));

commit;

-- Post-deployment notes:
-- - Backend operations should use the Service Role key and thus bypass RLS.
-- - For stricter client-side exposure, consider creating a limited view (e.g., public.user_profile)
--   exposing only safe columns (email, is_email_verified, created_at, last_login) and add RLS on that view.
-- - If passwords are changed, always compute hashed_password on the server (never on client).
-- - If you switch to link-based verification entirely, you can keep verification fields for audit/hardening.
