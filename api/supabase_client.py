import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# Respects RLS — use for all user-facing requests
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_ANON_KEY')
)

# Bypasses RLS — use ONLY for trusted server-side operations
# e.g. AI team saving scan results via X-Internal-Key
supabase_admin = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)
