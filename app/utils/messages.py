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
    """
    Parses the given email address and returns a tuple containing the username and domain.

    Args:
        email_address (str): The email address to be parsed.

    Returns:
        tuple[str, str]: A tuple containing the username and domain extracted from the email address.

    Raises:
        ValueError: If the email address is invalid.

    """
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
    """
    Creates an email message with the given parameters.
    Args:
        subject (str): The subject of the email.
        recipient (str | dict[str, str]): The recipient of the email. It can be either a string representing the email address or a dictionary with 'email' and 'display_name' keys.
        plain_text (str): The plain text content of the email.
        sender (str | dict[str, str]): The sender of the email. It can be either a string representing the email address or a dictionary with 'email' and 'display_name' keys.
        html_text (str | None, optional): The HTML content of the email. Defaults to None.
        in_reply_to (str | None, optional): The Message-ID of the email to which this email is a reply. Defaults to None.
        references (list[str] | None, optional): The list of Message-IDs that this email references. Defaults to None.
    Returns:
        tuple[EmailMessage, str]: A tuple containing the created EmailMessage object and the generated Message-ID.
    """
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
    """
    Sends an email using the provided SMTP server.

    Args:
        smtp (SMTP): The SMTP server to use for sending the email.
        subject (str): The subject of the email.
        recipient (str | dict[str, str]): The recipient of the email. Can be a string representing the email address or a dictionary with 'email' and 'display_name' keys.
        plain_text (str): The plain text content of the email.
        html_text (str | None, optional): The HTML content of the email. Defaults to None.
        sender (str | dict[str, str], optional): The sender of the email. Can be a string representing the email address or a dictionary with 'email' and 'display_name' keys. Defaults to {'email': settings.from_email, 'display_name': settings.from_name}.
        in_reply_to (str | None, optional): The message ID to which this email is a reply. Defaults to None.
        references (list[str] | None, optional): The list of message IDs that this email references. Defaults to None.

    Returns:
        str: The message ID of the sent email.

    Raises:
        HTTPException: If there is an error sending the email. The exception will contain the status code and error details.
    """
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
    """
    Renders an HTML template with the given template name and keyword arguments.

    Args:
        template (str): The name of the template file.
        **kwargs: Keyword arguments to be passed to the template.

    Returns:
        str: The rendered HTML template.

    Raises:
        TemplateNotFound: If the template file is not found.

    """
    ...
    env = Environment(loader=FileSystemLoader("app/templates"), enable_async=True)
    template: Template = env.get_template(template)
    rendered_template = await template.render_async(**kwargs)
    return rendered_template
