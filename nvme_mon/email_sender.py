import smtplib
from email.mime.text import MIMEText
import os
import ssl
import yaml
from dotenv import load_dotenv

from nvme_mon.paths import resource_path

load_dotenv(resource_path('.env'))

CONFIG_FILE_NAME = 'config.yaml'

if os.getenv("PRIVATE_CONFIG"): CONFIG_FILE_NAME = "config.private.yaml"

class EmailSender:

    def send_email(self, subject, body):
        recipient_email=os.env.get('RECIPIENT')
        email_address =os.env.get('EMAIL_ADDRESS')
        smtp_server = os.env.get('SMTP_SERVER')
        smtp_port = os.env.get('SMTP_PORT')
        email_password = os.env.get('EMAIL_PASSWORD')

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
            print(f"Error sending email: {e}")