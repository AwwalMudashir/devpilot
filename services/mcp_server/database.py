import os

import httpx
from dotenv import load_dotenv
from supabase import Client, ClientOptions, create_client
import truststore

load_dotenv()
truststore.inject_into_ssl()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

http_client = httpx.Client(
    http2=False,
    timeout=120.0,
)

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(httpx_client=http_client),
)
