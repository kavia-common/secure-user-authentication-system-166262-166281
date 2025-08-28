# Supabase Migration Queue (to run after new project credentials are configured)

Status: Pending (tools reported "Project removed." for the previous project)

When your new Supabase project is ready and credentials are set in authentication_backend/.env:

Option A (Recommended): Unified users schema
1) Open Supabase Dashboard -> SQL Editor
2) Paste and run file: authentication_backend/assets/supabase_users_unified.sql
3) Verify:
   - Table public.users exists
   - Indexes created: idx_users_email, idx_users_verification_expiry, idx_users_reset_expiry
   - Trigger trg_users_set_updated_at present
   - RLS enabled on public.users with basic owner policies

Option B (Legacy): app.* schema
1) Open Supabase Dashboard -> SQL Editor
2) Paste and run file: authentication_backend/assets/supabase_schema.sql
3) Verify:
   - Schema app exists
   - Tables app.profiles and app.verification_codes exist
   - Functions app.set_profile_email, app.purge_expired_codes, app.mark_email_verified created
   - Trigger trg_profiles_set_email present
   - RLS enabled with policies

Post migration:
- Go to Authentication -> URL Configuration
  - Site URL: set to your frontend URL
  - Redirect URLs: include http://localhost:3000/** and your production domain
- Start backend and test:
  - POST /auth/signup
  - POST /auth/send-code
  - POST /auth/verify
  - POST /auth/signin
  - POST /auth/forgot-password
  - POST /auth/reset-password
