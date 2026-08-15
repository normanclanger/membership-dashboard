from database import get_connection
from responses import (
    success,
    bad_request,
    forbidden
)


ALLOWED_READ_GROUPS = {
    "MembershipViewer",
    "MembershipAdmin",
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
        for group in groups.split(",")
        if group.strip()
    }


def can_read_payments(event):
    groups = get_user_groups(event)

    return bool(
        groups.intersection(ALLOWED_READ_GROUPS)
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


def lambda_handler(event, context):

    http_method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
    )

    if http_method != "GET":
        return bad_request({
            "error": "Only GET is supported"
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
