# Supabase configuration for Authentication System (Reinitialization with New Project)

This document consolidates the Supabase setup, required environment variables, and SQL to apply for both the legacy app.* schema and the newer unified public.users schema.

Current status:
- Automated Supabase checks returned: "Project removed." during tool execution. This indicates the previous Supabase project is unavailable. Proceed with the steps below after setting new credentials.

What you need to do now (high-level):
1) Create/obtain your NEW Supabase project URL and Service Role key.
2) Update environment files:
   - authentication_backend/.env (use .env.example as a guide)
   - authentication_frontend/.env (use .env.example as a guide)
3) In Supabase Dashboard:
   - Authentication -> URL Configuration:
     - Site URL: set to your frontend URL (e.g., http://localhost:3000 for local dev)
     - Add Redirect URLs:
       * http://localhost:3000/**
       * https://<your-domain>/**
   - Authentication -> Email templates: adjust if needed.
4) Apply one of the schemas:
   - Preferred: Unified users table (public.users):
     - Open authentication_backend/assets/supabase_users_unified.sql in Supabase SQL Editor and run it.
   - Legacy (if you need it): app.* schema:
     - Open authentication_backend/assets/supabase_schema.sql and run it.
5) Start services with the new env vars and verify.

Backend environment variables (REQUIRED):
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL
- SITE_URL

Frontend environment variables:
- REACT_APP_BACKEND_URL (REQUIRED)
- Optional: REACT_APP_SUPABASE_URL, REACT_APP_SUPABASE_ANON_KEY, REACT_APP_SITE_URL

Which schema should I use?
- Unified (recommended): Stores verification/reset codes directly on public.users; backend already uses this flow via PostgREST.
- Legacy: Separate app.profiles and app.verification_codes tables with RLS; still supported by assets for backward compatibility.

Apply SQL (Unified):
- Use file: authentication_backend/assets/supabase_users_unified.sql
- It will:
  - Drop legacy app.* tables (if any) and enum.
  - Create public.users with fields for verification/reset codes.
  - Add indexes, updated_at trigger, and RLS policies.

Apply SQL (Legacy):
- Use file: authentication_backend/assets/supabase_schema.sql
- It will:
  - Create app schema, app.profiles, app.verification_codes, needed functions/triggers.
  - Enable RLS and add policies.

Post-apply checks:
- Ensure public.users exists (Unified) or app.profiles/app.verification_codes exist (Legacy).
- Under Authentication -> Settings, verify URL configuration and redirects are correct.

Operations with the new project:
- The backend uses SUPABASE_SERVICE_ROLE_KEY (Service Role) exclusively; never expose this key to the frontend.
- The frontend talks only to the backend REST API.

Change log:
- Reinitialization guidance added due to project access error: "Project removed."
- Added .env.example files for backend and frontend.
- Confirmed backend code paths target unified public.users via PostgREST (no direct client access to codes).

Troubleshooting:
- If you see 403 not_admin from Admin API, verify you used the Service Role key (not anon key).
- If frontend fetch gets HTML instead of JSON, set REACT_APP_BACKEND_URL correctly and check CORS in backend.
