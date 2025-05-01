import smtplib
from email.mime.text import MIMEText

def send_email_alert(subject, body, to_email):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'shadowit-alerts@corp.com'
    msg['To'] = to_email

    with smtplib.SMTP('localhost') as server:
        server.send_message(msg)

if __name__ == "__main__":
    send_email_alert(
        "Unauthorized SaaS Usage Detected",
        "User 'alice@corp.com' accessed notion.so",
        "security@corp.com"
    )
