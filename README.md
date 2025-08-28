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
- Install Python dependencies and start FastAPI as per container instructions.