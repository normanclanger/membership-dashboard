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