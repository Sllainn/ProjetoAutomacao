from typing import Optional
from pydantic import BaseSettings

class Settings(BaseSettings):
    app_env: str = "staging"
    dispatch_enabled: bool = False
    
    # Variáveis mapeadas do seu .env
    log_level: Optional[str] = "INFO"
    database_url: Optional[str] = None
    postgres_password: Optional[str] = None
    dry_run: Optional[bool] = True
    default_timezone: Optional[str] = "America/Sao_Paulo"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()