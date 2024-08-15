from ..core.config import settings
from ..db.models import Complaint, Feedback, User
from ..utils.messages import get_html_from_template, send_email


async def reply_complaint(
    message: str,
    complaint: Complaint,
    sender: User,
) -> Feedback:
    """
    Sends a reply to a complaint and returns the feedback.
    Args:
        message (str): The reply message.
        complaint (Complaint): The complaint object.
        sender (User): The user who is sending the reply.
    Returns:
        Feedback: The feedback object.
    Raises:
        None
    """
    plain_text = message
    html_text = await get_html_from_template(
        template="feedback.html",
        message=message,
        username=complaint.user.username,
    )

    sender = {
        "email": sender.email,
        "display_name": sender.username,
    }

    # Send mail to customer
    message_id = await send_email(
        subject="Feedback received",
        recipient={
            "email": complaint.user.email,
            "display_name": complaint.user.username,
        },
        sender=sender,
        plain_text=plain_text,
        html_text=html_text,
    )
    feedback = Feedback(
        message_id=message_id,
        user_id=complaint.user_id,
        complaint_id=complaint.id,
        message=message,
    )
    return feedback


async def reply_feedback(message: str, feedback: Feedback, sender: User) -> Feedback:
    """
    Sends a reply to a feedback and returns the feedback.
    Args:
        message (str): The reply message.
        feedback (Feedback): The feedback object.
        sender (User): The user who is sending the reply.
    Returns:
        Feedback: The feedback object.
    Raises:
        None
    """
    plain_text = message
    html_text = (
        await get_html_from_template(
            template="feedback.html",
            message=message,
            username=feedback.user.username,
        )
        if sender.is_superuser
        else None
    )

    # Send mail to customer
    message_id = await send_email(
        subject="Feedback received",
        recipient=feedback.user.email,
        plain_text=plain_text,
        html_text=html_text,
        in_reply_to=feedback.message_id,
        references=[feedback.message_id],
    )
    reply = Feedback(
        message_id=message_id,
        user_id=feedback.user_id,
        complaint_id=feedback.complaint_id,
        message=message,
    )
    return reply
