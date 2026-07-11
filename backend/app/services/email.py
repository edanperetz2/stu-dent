import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, body: str) -> None:
    """Best-effort send via the local MailHog SMTP relay.

    Failures are logged, never raised: MailHog is dev/test-only infra (no
    paid email provider per the proposal's non-goals), so a flaky SMTP call
    must never block the DB transaction it's attached to.
    """
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(message)
    except OSError:
        logger.warning("Failed to send email to %s", to, exc_info=True)
