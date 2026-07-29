import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Every placeholder value this project has ever shipped in .env.example or
# as the Settings default -- if a real deployment's .env still has one of
# these, any token can be forged with a value anyone can read straight out
# of this public repo.
_KNOWN_PLACEHOLDER_JWT_SECRETS = frozenset(
    {"change-me-in-.env", "change-me-please-generate-a-random-secret"}
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://stu_dent:stu_dent@db:5432/stu_dent"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_minutes: int = 15

    registration_rate_limit_max_attempts: int = 10
    registration_rate_limit_window_minutes: int = 15
    # A separate, much higher per-IP-only ceiling -- a shared classroom/
    # clinic WiFi with dozens of *different* real people registering in one
    # onboarding session must not get bunched into the same tight counter
    # as repeated attempts at one specific email, or the last people
    # through the door get falsely locked out.
    registration_rate_limit_max_attempts_per_ip: int = 50

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    email_from: str = "noreply@stu-dent.local"

    reminder_lead_hours: int = 24
    job_poll_interval_seconds: int = 300
    unresolved_appointment_grace_hours: int = 24
    feedback_reminder_grace_hours: int = 24

    frontend_origins: str = "http://localhost:5173"

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: int = 30

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


def warn_if_placeholder_jwt_secret(jwt_secret_key: str) -> None:
    """A warning, not a startup crash -- this is a course project that needs
    to stay reliably reachable for grading, so misconfiguration should be
    loudly visible in the logs rather than taking the whole app down.
    Factored out (not inlined below) so a test can call it directly with a
    fixed string, instead of needing to reload this whole module (with its
    real Settings()/.env side effects) just to exercise the check.
    """
    if jwt_secret_key in _KNOWN_PLACEHOLDER_JWT_SECRETS:
        logger.warning(
            "JWT_SECRET_KEY is still set to a known placeholder value -- anyone can forge "
            "a valid access token for any user/role. Set a real random secret in .env "
            "before this is reachable from anywhere but localhost."
        )


settings = Settings()
warn_if_placeholder_jwt_secret(settings.jwt_secret_key)
