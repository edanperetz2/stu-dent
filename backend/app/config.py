from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://stu_dent:stu_dent@db:5432/stu_dent"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_minutes: int = 15


settings = Settings()
