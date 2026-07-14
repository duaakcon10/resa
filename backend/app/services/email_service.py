"""SMTP email service — send admin 2FA codes via email."""
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send email via SMTP. Returns True on success."""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        html = f"""
        <html><body style="font-family:monospace;background:#050510;color:#e0e0f0;padding:20px;">
        <div style="max-width:400px;margin:0 auto;background:#0a0a18;border:1px solid #1a1a35;border-radius:16px;padding:24px;">
        <h2 style="color:#00ff9d;margin:0 0 16px 0;">🔐 {subject}</h2>
        <p style="color:#7878a0;font-size:13px;">{body}</p>
        <p style="color:#4a4a68;font-size:11px;margin-top:20px;">C2 Command Center</p>
        </div></body></html>
        """
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html, "html"))

        def _send():
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(settings.SMTP_FROM, to, msg.as_string())
            server.quit()

        await asyncio.get_event_loop().run_in_executor(None, _send)
        return True
    except Exception as e:
        print(f"[email] SMTP error: {e}")
        return False


async def send_admin_code(email: str, code: str) -> bool:
    """Send 6-digit admin login code via email."""
    return await send_email(
        to=email,
        subject="Admin Login Code",
        body=f"Your admin login code is: {code}\nThis code expires in 5 minutes.\n\nC2 Command Center",
    )
