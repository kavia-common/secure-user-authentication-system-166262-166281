# secure-user-authentication-system-166262-166281

This project uses Supabase for Authentication and Postgres storage. Before running the backend:

1) Configure Supabase
- Open authentication_backend/assets/supabase.md and follow the steps.
- Apply the SQL in authentication_backend/assets/supabase_schema.sql using Supabase SQL Editor.

2) Configure environment
- Copy authentication_backend/.env.example to authentication_backend/.env and fill in values:
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY
  - SMTP_* and SITE_URL

3) Run backend
- Create virtualenv (optional), install dependencies, and start FastAPI:
  - cd authentication_backend
  - pip install -r requirements.txt
  - uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

Docs available at /docs and OpenAPI at /openapi.json (also exported to authentication_backend/interfaces/openapi.json via src/api/generate_openapi.py).