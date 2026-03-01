from supabase import create_client, Client

try:
    from config import settings
except ModuleNotFoundError:
    from src.agent.config import settings

_client: Client | None = None


def get_supabase_client() -> Client:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client
