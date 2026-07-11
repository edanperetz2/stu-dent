from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://stu_dent:stu_dent@db:5432/stu_dent"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_minutes: int = 15

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    email_from: str = "noreply@stu-dent.local"

    reminder_lead_hours: int = 24
    job_poll_interval_seconds: int = 300


settings = Settings()
