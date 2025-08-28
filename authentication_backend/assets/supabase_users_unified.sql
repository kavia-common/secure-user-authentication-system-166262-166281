-- Unified Users Table Migration
-- This script drops legacy tables (app.profiles, app.verification_codes) and
-- creates a new unified table public.users to support core flows:
-- - Signup (email + hashed password)
-- - Email verification via 6-digit code
-- - Password reset via code
-- The table is created in the public schema for maximum visibility in Supabase Dashboard.

begin;

-- 0) Ensure public schema exists (it always does in Supabase, but keep for clarity)
create schema if not exists public;

-- 1) Drop legacy tables if they exist (and dependent enum/type)
do $$
begin
  if exists (select from information_schema.tables where table_schema = 'app' and table_name = 'verification_codes') then
    execute 'drop table if exists app.verification_codes cascade';
  end if;

  if exists (select from information_schema.tables where table_schema = 'app' and table_name = 'profiles') then
    execute 'drop table if exists app.profiles cascade';
  end if;

  -- Drop enum type if exists
  if exists (select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace where n.nspname = 'app' and t.typname = 'code_purpose') then
    execute 'drop type app.code_purpose';
  end if;

  -- Optionally drop schema app if no longer used
  if exists (select 1 from information_schema.schemata where schema_name = 'app') then
    -- Only drop if empty to avoid accidentally removing other objects
    if not exists (select 1 from information_schema.tables where table_schema = 'app') then
      execute 'drop schema app';
    end if;
  end if;
end $$;

-- 2) Create unified users table in public schema
-- Note: This table is application-managed and NOT the same as auth.users.
-- You may choose to mirror auth.users email here for easier browsing and operations.
create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),       -- app-level user id
  email text not null unique,                          -- unique email for login
  hashed_password text not null,                       -- bcrypt/argon hash (never store plaintext)
  is_email_verified boolean not null default false,    -- flag set after successful verification

  -- Email verification code flow
  current_verification_code text,                      -- last issued 6-digit code (nullable)
  code_expires_at timestamptz,                         -- code expiry timestamp (nullable)
  code_attempts int not null default 0,                -- optional throttling for attempts

  -- Password reset code flow
  password_reset_code text,                            -- code sent for password reset (nullable)
  password_reset_expires timestamptz,                  -- expiry for reset code (nullable)

  -- Audit
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 3) Update trigger to maintain updated_at on row modification
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_users_set_updated_at on public.users;
create trigger trg_users_set_updated_at
before update on public.users
for each row execute procedure public.set_updated_at();

-- 4) Useful indexes
create index if not exists idx_users_email on public.users (lower(email));
create index if not exists idx_users_verification_expiry on public.users (code_expires_at);
create index if not exists idx_users_reset_expiry on public.users (password_reset_expires);

-- 5) RLS Policies (optional; comment out if you rely on service role exclusively)
-- For admin/backend access via Service Role, RLS can be enabled but your Service Role bypasses RLS.
-- Enable RLS to ensure public/anon access is restricted by default.
alter table public.users enable row level security;

-- Remove existing policies if re-running
drop policy if exists "Users: no select for anon" on public.users;
drop policy if exists "Users: owner can select self" on public.users;
drop policy if exists "Users: owner can update self-safe" on public.users;

-- Only authenticated users can select their own row (optional)
create policy "Users: owner can select self"
on public.users for select
to authenticated
using (auth.email() is not null and lower(email) = lower(auth.email()));

-- Only authenticated users can update their own record (limit what can be updated by clients)
-- Note: In most cases, updates will be performed by the backend using the Service Role.
create policy "Users: owner can update self-safe"
on public.users for update
to authenticated
using (auth.email() is not null and lower(email) = lower(auth.email()))
with check (auth.email() is not null and lower(email) = lower(auth.email()));

commit;

-- Notes:
-- - If you use this unified table instead of app.profiles/app.verification_codes,
--   update your backend to write/read the relevant fields here.
-- - Consider adding a foreign key to auth.users if desired:
--   auth_user_id uuid unique references auth.users(id) on delete cascade
--   and store it during signup for easier joins with auth.
