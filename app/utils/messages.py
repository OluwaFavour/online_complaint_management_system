from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import make_msgid
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


async def parse_email_address(email_address: str) -> tuple[str, str]:
    email_address = email_address.split("@")
    if len(email_address) != 2:
        raise ValueError("Invalid email address")
    return email_address[0], email_address[1]


async def create_email_message(
    subject: str,
    recipient: str | dict[str, str],
    plain_text: str,
    sender: str | dict[str, str],
    html_text: str | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> tuple[EmailMessage, str]:
    if isinstance(recipient, dict):
        to_email = recipient["email"]
        to_display_name = recipient.get("display_name", "")
    else:
        to_email = recipient
        to_display_name = ""

    if isinstance(sender, dict):
        from_email = sender["email"]
        from_display_name = sender.get("display_name", "")
    elif isinstance(sender, str):
        from_email = sender
        from_display_name = ""

    from_name, from_domain = await parse_email_address(from_email)
    to_name, to_domain = await parse_email_address(to_email)

    # Generate unique Message-ID
    message_id = make_msgid()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = Address(from_display_name, from_name, from_domain)
    message["To"] = Address(to_display_name, to_name, to_domain)
    message["Message-ID"] = message_id

    # Add In-Reply-To and References headers if provided
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = ", ".join(references)

    message.set_content(plain_text)

    if html_text:
        message.add_alternative(html_text, subtype="html")

    return message, message["Message-ID"]


async def send_email(
    smtp: SMTP,
    subject: str,
    recipient: str | dict[str, str],
    plain_text: str,
    html_text: str | None = None,
    sender: str | dict[str, str] = {
        "email": settings.from_email,
        "display_name": settings.from_name,
    },
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> str:
    try:
        message, message_id = await create_email_message(
            subject=subject,
            recipient=recipient,
            plain_text=plain_text,
            html_text=html_text,
            sender=sender,
            in_reply_to=in_reply_to,
            references=references,
        )
        await smtp.send_message(message)
        return message_id
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid email address", "error": str(e)},
        )
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


async def get_html_from_template(template: str, **kwargs) -> str:
    env = Environment(loader=FileSystemLoader("app/templates"), enable_async=True)
    template: Template = env.get_template(template)
    rendered_template = await template.render_async(**kwargs)
    return rendered_template
