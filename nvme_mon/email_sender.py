import smtplib
from email.mime.text import MIMEText
import os
import ssl
import yaml

from nvme_mon.paths import resource_path

class EmailSender:

    def __init__(self, config_file):
        if config_file is None:
            config_file = resource_path('config.yaml')
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)['email_settings']

    def send_email(self, subject, body):
        recipient_email=self.config['recipient']
        email_address = self.config['email_address']
        smtp_server = self.config['smtp_server']
        smtp_port = self.config['smtp_port']
        email_password = self.config['email_password']

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