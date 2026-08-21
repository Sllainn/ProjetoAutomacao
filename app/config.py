
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "staging"
    dispatch_enabled: bool = False
    
    # Variáveis mapeadas do seu .env
    log_level: str | None = "INFO"
    database_url: str | None = None
    postgres_password: str | None = None
    dry_run: bool | None = True
    default_timezone: str | None = "America/Sao_Paulo"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()