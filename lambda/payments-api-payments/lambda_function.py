import json

from database import get_connection
from responses import (
    success,
    created,
    bad_request,
    forbidden,
    response
)


ALLOWED_READ_GROUPS = {
    "MembershipViewer",
    "MembershipAdmin",
    "PaymentAdmin",
    "ApplicationAdmin"
}

ALLOWED_WRITE_GROUPS = {
    "PaymentAdmin",
    "ApplicationAdmin"
}

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

def get_user_sub(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    return claims.get("sub")

def can_read_payments(event):
    groups = get_user_groups(event)

    return bool(
        groups.intersection(ALLOWED_READ_GROUPS)
    )

def can_write_payments(event):
    groups = get_user_groups(event)

    return bool(
        groups.intersection(ALLOWED_WRITE_GROUPS)
    )

def payment_from_row(row):
    return {
        "id": row[0],
        "payment_date": row[1].isoformat(),
        "statement_reference": row[2],
        "member_id": row[3],
        "membership_number": row[4],
        "first_name": row[5],
        "surname": row[6],
        "subscription_amount": float(row[7]),
        "gift_amount": float(row[8]),
        "calendar_year": row[9]
    }

def create_payments(event):
    if not can_write_payments(event):
        return forbidden({
            "error": "You do not have permission to add payments"
        })

    created_by = get_user_sub(event)

    if not created_by:
        return forbidden({
            "error": "Authenticated user identity is unavailable"
        })

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request({
            "error": "Request body must contain valid JSON"
        })

    payments = body.get("payments")

    if not isinstance(payments, list) or not payments:
        return bad_request({
            "error": "payments must be a non-empty list"
        })

    required_fields = {
        "payment_date",
        "statement_reference",
        "member_id",
        "subscription_amount",
        "gift_amount",
        "calendar_year"
    }

    prepared = []

    for index, payment in enumerate(payments):

        if not isinstance(payment, dict):
            return bad_request({
                "error": "Each payment must be an object",
                "index": index
            })

        missing = sorted(
            required_fields - set(payment)
        )

        if missing:
            return bad_request({
                "error": "Payment is missing required fields",
                "index": index,
                "fields": missing
            })

        try:
            member_id = int(payment["member_id"])
        except (TypeError, ValueError):
            return bad_request({
                "error": "member_id must be a number",
                "index": index
            })

        try:
            calendar_year = int(payment["calendar_year"])
        except (TypeError, ValueError):
            return bad_request({
                "error": "calendar_year must be a number",
                "index": index
            })

        try:
            subscription_amount = float(
                payment["subscription_amount"]
            )
            gift_amount = float(
                payment["gift_amount"]
            )
        except (TypeError, ValueError):
            return bad_request({
                "error": "Payment amounts must be numeric",
                "index": index
            })

        prepared.append({
            "payment_date": payment["payment_date"],
            "statement_reference":
                str(payment["statement_reference"]),
            "member_id": member_id,
            "subscription_amount":
                subscription_amount,
            "gift_amount":
                gift_amount,
            "calendar_year": calendar_year
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # Confirm all members exist before writing anything
            # -------------------------------------------------

            member_ids = {
                payment["member_id"]
                for payment in prepared
            }

            cur.execute(
                """
                SELECT id
                FROM members
                WHERE id = ANY(%s);
                """,
                (list(member_ids),)
            )

            existing_member_ids = {
                row[0]
                for row in cur.fetchall()
            }

            missing_member_ids = sorted(
                member_ids - existing_member_ids
            )

            if missing_member_ids:
                return bad_request({
                    "error": "One or more members do not exist",
                    "member_ids": missing_member_ids
                })

            # -------------------------------------------------
            # Check for possible duplicate payments
            # -------------------------------------------------

            duplicates = []

            for payment in prepared:
                cur.execute(
                    """
                    SELECT id
                    FROM payments
                    WHERE statement_reference = %s
                      AND member_id = %s
                    LIMIT 1;
                    """,
                    (
                        payment["statement_reference"],
                        payment["member_id"]
                    )
                )

                existing = cur.fetchone()

                if existing:
                    duplicates.append({
                        "statement_reference":
                            payment["statement_reference"],
                        "member_id":
                            payment["member_id"],
                        "existing_payment_id":
                            existing[0]
                    })

            if duplicates:
                return response(
                    409,
                    {
                        "error": "Possible duplicate payment(s)",
                        "duplicates": duplicates
                    }
                )

            # -------------------------------------------------
            # Insert the complete batch
            # -------------------------------------------------

            created_payments = []

            for payment in prepared:

                cur.execute(
                    """
                    INSERT INTO payments (
                        payment_date,
                        statement_reference,
                        member_id,
                        subscription_amount,
                        gift_amount,
                        calendar_year,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        payment_date,
                        statement_reference,
                        member_id,
                        subscription_amount,
                        gift_amount,
                        calendar_year;
                    """,
                    (
                        payment["payment_date"],
                        payment["statement_reference"],
                        payment["member_id"],
                        payment["subscription_amount"],
                        payment["gift_amount"],
                        payment["calendar_year"],
                        created_by
                    )
                )

                row = cur.fetchone()

                created_payments.append({
                    "id": row[0],
                    "payment_date": row[1].isoformat(),
                    "statement_reference": row[2],
                    "member_id": row[3],
                    "subscription_amount":
                        float(row[4]),
                    "gift_amount":
                        float(row[5]),
                    "calendar_year": row[6]
                })

            conn.commit()

            return created({
                "payments": created_payments
            })

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def lambda_handler(event, context):

    http_method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
    )

    if http_method == "POST":
        return create_payments(event)

    if http_method != "GET":
        return bad_request({
            "error": "Only GET and POST are supported"
        })

    if not can_read_payments(event):
        return forbidden({
            "error": "You do not have permission to read payments"
        })

    query_parameters = (
        event.get("queryStringParameters") or {}
    )

    member_id = query_parameters.get("member_id")
    calendar_year = query_parameters.get("calendar_year")

    if member_id:
        try:
            member_id = int(member_id)
        except ValueError:
            return bad_request({
                "error": "member_id must be a number"
            })

    if calendar_year:
        try:
            calendar_year = int(calendar_year)
        except ValueError:
            return bad_request({
                "error": "calendar_year must be a number"
            })

    conditions = []
    values = []

    if member_id is not None:
        conditions.append("p.member_id = %s")
        values.append(member_id)

    if calendar_year is not None:
        conditions.append("p.calendar_year = %s")
        values.append(calendar_year)

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                f"""
                SELECT
                    p.id,
                    p.payment_date,
                    p.statement_reference,
                    p.member_id,

                    m.membership_number,
                    m.first_name,
                    m.surname,

                    p.subscription_amount,
                    p.gift_amount,
                    p.calendar_year

                FROM payments p

                JOIN members m
                    ON p.member_id = m.id

                {where_clause}

                ORDER BY
                    p.payment_date,
                    p.id;
                """,
                values
            )

            rows = cur.fetchall()

            return success({
                "payments": [
                    payment_from_row(row)
                    for row in rows
                ]
            })

    finally:
        conn.close()
