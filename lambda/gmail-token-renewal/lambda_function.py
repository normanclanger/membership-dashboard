
import os
import json
import time
import hmac
import hashlib
import secrets
import base64
import logging
import html

import boto3

from google_auth_oauthlib.flow import Flow


def get_user_groups(event):

    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    groups = claims.get("cognito:groups", "")

    if not groups:
        return set()

    groups = groups.strip("[]")

    if not groups:
        return set()

    return {
        group.strip().strip("'\"")
        for group in groups.replace(",", " ").split()
        if group.strip()
    }


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]

STATE_COOKIE = "gmail_oauth_state"
STATE_LIFETIME = 600  # 10 minutes

GOOGLE_CLIENT_SECRET_ARN = os.environ["GOOGLE_CLIENT_SECRET_ARN"]
GMAIL_TOKEN_SECRET_ARN = os.environ["GMAIL_TOKEN_SECRET_ARN"]
OAUTH_REDIRECT_URI = os.environ["OAUTH_REDIRECT_URI"]
OAUTH_STATE_SECRET = os.environ["OAUTH_STATE_SECRET"].encode("utf-8")

secrets_manager = boto3.client("secretsmanager")


# ---------------------------------------------------------
# HTTP responses
# ---------------------------------------------------------

def response(status_code, body, headers=None, cookies=None):

    result = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store"
        },
        "body": body,
        "isBase64Encoded": False
    }

    if headers:
        result["headers"].update(headers)

    if cookies:
        result["cookies"] = cookies

    return result


def html_page(message, heading="Gmail authorisation"):

    safe_message = html.escape(message)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{heading}</title>
</head>
<body style="font-family: sans-serif; max-width: 650px;
             margin: 60px auto; padding: 20px; line-height: 1.5;">
    <h1>{heading}</h1>
    <p>{safe_message}</p>
    <p>You can close this window and return to the Gift Aid dashboard.</p>
</body>
</html>"""


def html_response(status_code, message, heading="Gmail authorisation",
                  cookies=None):

    return response(
        status_code,
        html_page(message, heading),
        cookies=cookies
    )


# ---------------------------------------------------------
# Secrets Manager
# ---------------------------------------------------------

def get_secret(secret_arn):

    result = secrets_manager.get_secret_value(
        SecretId=secret_arn
    )

    if "SecretString" not in result:
        raise ValueError("Secret does not contain a SecretString")

    return result["SecretString"]


# ---------------------------------------------------------
# OAuth state signing
# ---------------------------------------------------------

def base64url_encode(value):

    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def base64url_decode(value):

    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        value + padding
    )


def create_state():

    nonce = secrets.token_urlsafe(32)

    payload = {
        "iat": int(time.time()),
        "nonce": nonce
    }

    encoded_payload = base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    signature = hmac.new(
        OAUTH_STATE_SECRET,
        encoded_payload.encode("ascii"),
        hashlib.sha256
    ).digest()

    state = encoded_payload + "." + base64url_encode(signature)

    return state, nonce


def validate_state(state):

    try:
        encoded_payload, supplied_signature = state.split(".")

        expected_signature = hmac.new(
            OAUTH_STATE_SECRET,
            encoded_payload.encode("ascii"),
            hashlib.sha256
        ).digest()

        supplied_signature_bytes = base64url_decode(
            supplied_signature
        )

        if not hmac.compare_digest(
            expected_signature,
            supplied_signature_bytes
        ):
            logging.error("OAuth state failed signature check")
            return False

        payload = json.loads(
            base64url_decode(encoded_payload)
        )

        issued_at = int(payload["iat"])
        nonce = payload.get("nonce")

        now = int(time.time())

        logging.info(
            "OAuth state timestamps: issued_at=%s, now=%s, age=%s",
            issued_at, now, now - issued_at
        )

        if not nonce:
            logging.error("OAuth state has no nonce")
            return False

        if issued_at > now + 60:
            logging.error("OAuth state timestamp is in the future")
            return False

        if now - issued_at > STATE_LIFETIME:
            logging.error("OAuth state has expired")
            return False

        logging.info("OAuth state validation successful")
        return True

    except Exception:
        logging.exception("OAuth state validation raised an exception")
        return False


# ---------------------------------------------------------
# Cookie handling
# ---------------------------------------------------------

def get_cookie(event, name):

    # HTTP API payload format 2.0 provides a cookies array.
    for cookie in event.get("cookies", []):

        key, separator, value = cookie.partition("=")

        if separator and key.strip() == name:
            return value.strip()

    # Fallback to the Cookie header.
    headers = event.get("headers") or {}

    cookie_header = headers.get("cookie", "")

    for item in cookie_header.split(";"):

        key, separator, value = item.strip().partition("=")

        if separator and key == name:
            return value.strip()

    return None


def set_state_cookie(nonce):

    return (
        f"{STATE_COOKIE}={nonce}; "
        "Path=/api/gmail-renew/callback; "
        "Max-Age=600; "
        "Secure; "
        "HttpOnly; "
        "SameSite=Lax"
    )


def clear_state_cookie():

    return (
        f"{STATE_COOKIE}=; "
        "Path=/api/gmail-renew/callback; "
        "Max-Age=0; "
        "Secure; "
        "HttpOnly; "
        "SameSite=Lax"
    )


# ---------------------------------------------------------
# Google OAuth flow
# ---------------------------------------------------------

def create_oauth_flow(state=None):

    client_config = json.loads(
        get_secret(GOOGLE_CLIENT_SECRET_ARN)
    )

    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=OAUTH_REDIRECT_URI
    )


# ---------------------------------------------------------
# Start authorisation
# ---------------------------------------------------------

def handle_start(event):


    groups = get_user_groups(event)


    if "ApplicationAdmin" not in groups:

        return html_response(
            403,
            "You are not authorised to renew Gmail access.",
            "Access denied"
        )

    try:

        state, nonce = create_state()

        flow = create_oauth_flow()

        authorization_url, _ = flow.authorization_url(
            state=state,
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true"
        )

        return response(
            302,
            "",
            headers={
                "Location": authorization_url
            },
            cookies=[
                set_state_cookie(nonce)
            ]
        )

    except Exception:

        logging.exception("Unable to start Gmail authorisation")

        return html_response(
            500,
            "Unable to start Gmail authorisation. Please try again.",
            "Renewal could not be started"
        )


# ---------------------------------------------------------
# Google callback
# ---------------------------------------------------------

def handle_callback(event):

    query = event.get("queryStringParameters") or {}

    state = query.get("state")
    code = query.get("code")
    google_error = query.get("error")

    cookie_nonce = get_cookie(event, STATE_COOKIE)

    # Validate state before processing either success or error.
    if not state or not validate_state(state, cookie_nonce):

        return html_response(
            400,
            "The authorisation request has expired or is invalid. "
            "Please start the renewal process again.",
            "Invalid authorisation request",
            cookies=[clear_state_cookie()]
        )

    if google_error:

        logging.warning(
            "Google authorisation returned error: %s",
            google_error
        )

        return html_response(
            400,
            "Google authorisation was not completed. "
            "Please try again.",
            "Authorisation not completed",
            cookies=[clear_state_cookie()]
        )

    if not code:

        return html_response(
            400,
            "Google did not return an authorisation code.",
            "Authorisation failed",
            cookies=[clear_state_cookie()]
        )

    try:

        flow = create_oauth_flow(state=state)

        # Exchange Google's single-use authorisation code.
        flow.fetch_token(code=code)

        credentials = flow.credentials

        # Never replace the working token unless Google
        # has actually supplied a new refresh token.
        if not credentials.refresh_token:

            logging.error(
                "Google returned no refresh token"
            )

            return html_response(
                500,
                "Google did not issue a new refresh token. "
                "Your existing email authorisation has been left unchanged.",
                "Renewal unsuccessful",
                cookies=[clear_state_cookie()]
            )

        # Save in the same JSON format used by the email Lambda.
        token_json = credentials.to_json()

        secrets_manager.put_secret_value(
            SecretId=GMAIL_TOKEN_SECRET_ARN,
            SecretString=token_json
        )

        logging.info(
            "Gmail OAuth token successfully renewed"
        )

        return html_response(
            200,
            "Your Gmail authorisation has been renewed successfully. "
            "The Gift Aid email service can continue using the new token.",
            "Renewal successful",
            cookies=[clear_state_cookie()]
        )

    except Exception:

        logging.exception(
            "Gmail OAuth callback failed"
        )

        return html_response(
            500,
            "The Gmail authorisation could not be renewed. "
            "Your existing token has not been deliberately replaced.",
            "Renewal failed",
            cookies=[clear_state_cookie()]
        )


# ---------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------

def lambda_handler(event, context):

    path = event.get("rawPath", "")
    method = (
        event.get("requestContext", {})
             .get("http", {})
             .get("method", "")
    )

    logging.info(
        "Gmail renewal request: %s %s",
        method,
        path
    )

    if method == "GET" and path.endswith("/gmail-renew/start"):
        return handle_start(event)

    if method == "GET" and path.endswith("/gmail-renew/callback"):
        return handle_callback(event)

    return html_response(
        404,
        "The requested Gmail renewal endpoint was not found.",
        "Not found"
    )
