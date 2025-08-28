-- SCHEMA: create application schema, profile, and verification codes tables.

create schema if not exists app;

create table if not exists app.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  is_email_verified boolean not null default false
);

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

create type if not exists app.code_purpose as enum ('email_verification', 'password_reset');

create table if not exists app.verification_codes (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  purpose app.code_purpose not null,
  code text not null,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint uq_active_code unique (user_id, purpose, code)
);

create index if not exists idx_verification_codes_user_purpose on app.verification_codes(user_id, purpose);
create index if not exists idx_verification_codes_email_purpose on app.verification_codes(email, purpose);
create index if not exists idx_verification_codes_expires on app.verification_codes(expires_at);
create index if not exists idx_verification_codes_consumed on app.verification_codes(consumed_at);

create or replace function app.purge_expired_codes()
returns void
language plpgsql
security definer
as $$
  delete from app.verification_codes
  where (expires_at < now() - interval '1 hour')
     or (consumed_at is not null and consumed_at < now() - interval '1 hour');
$$;

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

-- SECURITY: RLS

alter table app.profiles enable row level security;
alter table app.verification_codes enable row level security;

drop policy if exists "Profiles: owner can select" on app.profiles;
create policy "Profiles: owner can select"
on app.profiles for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "Profiles: owner can insert" on app.profiles;
create policy "Profiles: owner can insert"
on app.profiles for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "Profiles: owner can update" on app.profiles;
create policy "Profiles: owner can update"
on app.profiles for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Codes: owner can select own" on app.verification_codes;
create policy "Codes: owner can select own"
on app.verification_codes for select
to authenticated
using (auth.uid() = user_id);

-- No insert/update/delete policies on verification_codes for authenticated users (server-only writes).

