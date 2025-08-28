# Backend ENV Checklist (New Supabase Project)

Ensure these are set in authentication_backend/.env:

- SUPABASE_URL = https://<project-ref>.supabase.co
- SUPABASE_SERVICE_ROLE_KEY = <service-role-jwt>
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL
- SITE_URL = http://localhost:3000 (dev) or your production URL

Optional:
- FRONTEND_BASE_URL for strict CORS in production
- LOG_LEVEL, APP_ENV, APP_DEBUG

After setting .env:
- pip install -r requirements.txt
- uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
