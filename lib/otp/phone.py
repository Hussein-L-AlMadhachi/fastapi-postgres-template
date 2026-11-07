"""Send a login OTP by SMS.

Replace the body with a real provider call (Twilio, SNS, ...).
"""

from lib import config
from logs import logger


async def send_otp_phone(phone_number: str, otp: str) -> None:
    if config.is_dev():
        logger.info("otp.phone", phone_number=phone_number, otp=otp)
    else:
        logger.warning("otp.phone.not_configured", phone_number=phone_number)
