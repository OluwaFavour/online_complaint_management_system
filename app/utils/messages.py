from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from aiosmtplib import (
    SMTP,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPDataError,
    SMTPException,
)

from fastapi import HTTPException, status

from jinja2 import FileSystemLoader, Environment, Template

from ..core.config import settings


async def create_email_message(
    subject: str,
    recipient: str,
    plain_text: str,
    sender: str,
    html_text: str | None = None,
) -> MIMEText | MIMEMultipart:
    if html_text:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(plain_text, "plain"))
        message.attach(MIMEText(html_text, "html"))
    else:
        message = MIMEText(plain_text, "plain")

    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient

    return message


async def send_email(
    smtp: SMTP,
    subject: str,
    recipient: str,
    plain_text: str,
    html_text: str | None = None,
    sender: str = settings.from_email,
) -> None:
    try:
        message = await create_email_message(
            subject=subject,
            recipient=recipient,
            plain_text=plain_text,
            html_text=html_text,
            sender=sender,
        )
        await smtp.sendmail(sender, recipient, message.as_string())
    except SMTPRecipientsRefused as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Recipient refused", "error": str(e)},
        )
    except SMTPSenderRefused as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Sender refused", "error": str(e)},
        )
    except SMTPDataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Data error", "error": str(e)},
        )
    except SMTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Internal server error when sending mail",
                "error": str(e),
            },
        )
    else:
        return None


async def get_html_from_template(template: str, **kwargs) -> str:
    env = Environment(loader=FileSystemLoader("app/templates"), enable_async=True)
    template: Template = env.get_template(template)
    rendered_template = await template.render_async(**kwargs)
    return rendered_template
