from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    secret_key: SecretStr = Field(min_length=32)
    database_url: str
    log_level: str = 'INFO'
    sql_echo: bool = False
    seed_catalog: bool = False
    allowed_hosts: list[str] = ['localhost', '127.0.0.1', 'testserver', 'web']
    redis_url: str = 'redis://redis:6379/0'
    rate_limit_enabled: bool = False
    sentry_dsn: str | None = None


settings = Settings()
SECRET_KEY = settings.secret_key.get_secret_value()
ALGORITHM = 'HS256'
