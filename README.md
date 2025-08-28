# secure-user-authentication-system-166262-166281

This project uses Supabase for Authentication and Postgres storage.

Reinitialization with a new Supabase project:
- If you created a new Supabase project, update:
  - authentication_backend/.env (see .env.example)
  - authentication_frontend/.env (see .env.example)
- Then apply SQL from either:
  - authentication_backend/assets/supabase_users_unified.sql (recommended), or
  - authentication_backend/assets/supabase_schema.sql (legacy)
- See authentication_backend/assets/supabase.md for the complete guide.

Before running the backend:

1) Configure Supabase (Dashboard settings)
- Authentication -> URL Configuration:
  - Set Site URL to your frontend URL (e.g., http://localhost:3000 for local dev).
  - Add redirect URLs:
    * http://localhost:3000/**
    * https://yourapp.com/**
- Authentication -> Email templates: adjust if needed.

2) Configure environment
- Create authentication_backend/.env and fill in values (backend-only names):
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY  (Service Role key; DO NOT use anon/public key)
  - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL
  - SITE_URL (frontend public URL used in email links)

Notes:
- Do not use frontend-style env names in the backend (avoid REACT_APP_* or NEXT_PUBLIC_*). They are ignored by the backend and may indicate misconfiguration.

3) Run backend
- Create virtualenv (optional), install dependencies, and start FastAPI:
  - cd authentication_backend
  - pip install -r requirements.txt
  - uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

Docs available at /docs and OpenAPI at /openapi.json (also exported to authentication_backend/interfaces/openapi.json via src/api/generate_openapi.py).