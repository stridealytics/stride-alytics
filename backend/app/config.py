"""Pydantic-based settings using environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    APP_NAME: str = "StrideAlytics"
    DEBUG: bool = False

    # --- Database (Supabase / PostgreSQL) ---
    DATABASE_URL: str | None = None
    # Keep these small: Supabase free allows few connections and Render free has 512 MB RAM.
    DATABASE_POOL_SIZE: int = 3
    DATABASE_MAX_OVERFLOW: int = 2

    # --- Auth (Supabase) ---
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # Optional: "https://<ref>.supabase.co/auth/v1/.well-known/jwks.json" is derived from
    # SUPABASE_URL when unset. Used for projects that sign tokens with asymmetric keys.
    SUPABASE_JWKS_URL: str | None = None

    # --- Registration ---
    # Personal-use app: self-service signup is OFF. Create your user in the Supabase dashboard
    # (and turn "Allow new users to sign up" off there too). Always allowed in development.
    ALLOW_SIGNUP: bool = False

    # --- Email ---
    SENDGRID_API_KEY: str | None = None

    # --- Notifications ---
    SLACK_WEBHOOK: str | None = None

    # --- App ---
    # Defaults to production so dev-only shortcuts (dev auth tokens) are off
    # unless ENVIRONMENT=development is set explicitly (see .env.example).
    ENVIRONMENT: str = "production"

    # --- CORS ---
    CORS_ORIGINS: str = "*"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
