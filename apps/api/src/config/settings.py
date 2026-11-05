from pydantic_settings import BaseSettings

# Browsers on the same machine or the local network (e.g. opening the UI
# at http://192.168.1.12:3000 from another device) must be allowed to
# call the API. An explicit list alone missed LAN IPs, which left the
# dashboard unable to reach the API when opened via the machine's IP.
DEFAULT_CORS_ORIGIN_REGEX = (
    r"https?://("
    r"localhost|127\.0\.0\.1|0\.0\.0\.0"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"  # CGNAT / Tailscale
    r"|[a-zA-Z0-9-]+\.local"  # mDNS hostnames, e.g. my-laptop.local
    r")(:\d+)?"
)


class Settings(BaseSettings):
    # Defaults match docker-compose service names. For a local shell,
    # export DATABASE_URL / REDIS_URL / TEMPORAL_HOST (see RUNBOOK.md).
    database_url: str = "postgresql+psycopg://solunex:solunex@postgres:5432/solunex"
    redis_url: str = "redis://redis:6379/0"
    temporal_host: str = "temporal:7233"
    temporal_task_queue: str = "avos-production"
    # Tests set this so pooled async connections are never reused across
    # event loops (FastAPI's TestClient runs the app on its own loop).
    database_nullpool: bool = False

    assets_storage_path: str = "/data/assets"

    # Comma-separated exact origins, plus a regex for local/LAN hosts.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = DEFAULT_CORS_ORIGIN_REGEX

    # Placeholder per-tool-call cost until real provider pricing exists.
    placeholder_cost_per_tool_call: float = 0.01


settings = Settings()
