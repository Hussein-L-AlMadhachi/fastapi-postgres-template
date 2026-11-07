"""Send a login OTP by email.

Replace the body with a real provider call (SMTP, SES, Resend, ...).
"""

from lib import config
from logs import logger


async def send_otp_email(email: str, otp: str) -> None:
    if config.is_dev():
        logger.info("otp.email", email=email, otp=otp)
    else:
        logger.warning("otp.email.not_configured", email=email)
