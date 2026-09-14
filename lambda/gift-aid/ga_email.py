import base64
import json
from email.message import EmailMessage

import boto3

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SECRET_NAME = "suffolk-guild/gmail-gift-aid"

GMAIL_USER = "sgrtreasurer@gmail.com"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


def get_gmail_credentials():

    secrets_manager = boto3.client(
        "secretsmanager"
    )

    response = secrets_manager.get_secret_value(
        SecretId=SECRET_NAME
    )

    token_json = response["SecretString"]

    credentials = Credentials.from_authorized_user_info(
        json.loads(token_json),
        SCOPES
    )

    if credentials.expired:

        if not credentials.refresh_token:

            raise RuntimeError(
                "Gmail credentials have expired and no refresh token is available"
            )

        credentials.refresh(
            Request()
        )

    return credentials


def send_email(
    recipient,
    subject,
    body
):

    if not recipient:
        raise ValueError(
            "Email recipient is required"
        )

    if not subject:
        raise ValueError(
            "Email subject is required"
        )

    if not body:
        raise ValueError(
            "Email body is required"
        )

    credentials = get_gmail_credentials()

    gmail = build(
        "gmail",
        "v1",
        credentials=credentials
    )

    message = EmailMessage()

    message["From"] = GMAIL_USER
    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(
        body
    )

    encoded_message = (
        base64.urlsafe_b64encode(
            message.as_bytes()
        )
        .decode()
    )

    response = (
        gmail.users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": encoded_message
            }
        )
        .execute()
    )

    return response["id"]
    
def send_gift_aid_submission_email(
    recipient,
    declarer_name,
    gift_aid_reference,
    action,
    status,
    declaration_text,
    covered_members,
):

    if status == "CONFIRMED":

        if action == "AFFIRMED":
            heading = (
                "Your Gift Aid declaration has been received "
                "and confirmed."
            )

        elif action == "UPDATED":
            heading = (
                "Your Gift Aid declaration update has been "
                "received and confirmed."
            )

        elif action == "CANCELLED":
            heading = (
                "Your decision to cancel you Gift Aid declaration "
                "has been received."
            )

        elif action == "DECLINED":
            heading = (
                "Your decision not to complete a Gift Aid declaration has been "
                "received."
            )

        else:
            heading = (
                "Your Gift Aid submission has been received "
                "and confirmed."
            )

    else:

        heading = (
            "Your Gift Aid submission has been received "
            "and will be reviewed by the treasurer."
        )

    covered_text = ""

    if covered_members:

        covered_lines = []

        for member in covered_members:

            name = (
                f"{member.get('first_name', '')} "
                f"{member.get('surname', '')}"
            ).strip()

            membership_number = (
                member.get("membership_number")
            )

            if membership_number:

                covered_lines.append(
                    f"- {name} "
                    f"(membership number {membership_number})"
                )

            else:

                covered_lines.append(
                    f"- {name}"
                )

        covered_text = (
            "\n\nPeople covered by this declaration:\n"
            + "\n".join(covered_lines)
        )

    else:

        covered_text = (
            "\n\nPeople covered by this declaration:\n"
            "- None"
        )

    body = f"""Dear {declarer_name},

{heading}

Gift Aid reference: {gift_aid_reference}
Submission type: {action}
Submission status: {status}

Your submitted declaration text was:

"{declaration_text}"
{covered_text}

Please keep this email for your records.

Suffolk Guild of Ringers
"""

    return send_email(
        recipient=recipient,
        subject=(
            f"Gift Aid declaration "
            f"{gift_aid_reference} - {action}"
        ),
        body=body,
    )