import smtplib
from email.mime.text import MIMEText
import os
import ssl
import logging
from throttled import Throttled, rate_limiter, exceptions

log = logging.getLogger(__name__)

class EmailSender:

    def __init__(self, rate_limit):
        self.throttled = Throttled(key="send_email", quota=rate_limiter.per_hour(rate_limit))

    def send_email(self, subject, body):
        result = self.throttled.limit(key="send_email")
        if result.limited:
            raise exceptions.LimitedError
        recipient_email=os.environ.get('RECIPIENT')
        email_address =os.environ.get('EMAIL_ADDRESS')
        smtp_server = os.environ.get('SMTP_SERVER')
        smtp_port = os.environ.get('SMTP_PORT')
        email_password = os.environ.get('EMAIL_PASSWORD')

        log.debug(f"email {email_address}")
        log.debug(f"password {"********" if email_password else "NOT SET"}")
        log.debug(f"recipient {recipient_email}")
        log.debug(f"server {smtp_server}")
        log.debug(f"port {smtp_port}")

        msg = MIMEText(body, 'plain')
        msg['From'] = email_address
        msg['To'] = recipient_email
        msg['Subject'] = subject

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(email_address, email_password)
                server.sendmail(email_address, recipient_email, msg.as_string())
        except Exception as e:
            raise e