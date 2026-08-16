import json
from decimal import Decimal, InvalidOperation

from database import get_connection
from responses import (
    success,
    created,
    bad_request,
    forbidden,
    not_found
)


ALLOWED_WRITE_GROUPS = {
    "PaymentAdmin",
    "ApplicationAdmin"
}


def get_claims(event):
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )


def get_user_groups(event):
    claims = get_claims(event)

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


def get_user_id(event):
    claims = get_claims(event)

    return claims.get("sub")


def can_write_imports(event):
    groups = get_user_groups(event)

    return bool(
        groups.intersection(ALLOWED_WRITE_GROUPS)
    )


def import_from_row(row):
    return {
        "id": row[0],
        "created_at": row[1].isoformat(),
        "created_by": row[2],
        "status": row[3]
    }


def line_from_row(row):
    return {
        "id": row[0],
        "statement_reference": row[1],
        "payment_date": row[2].isoformat(),
        "statement_amount": (
            str(row[3])
            if row[3] is not None
            else None
        ),
        "statement_type": row[4],
        "description": row[5],
        "action": row[6]
    }


def item_from_row(row):
    return {
        "id": row[0],
        "member_id": row[1],
        "subscription_amount": (
            str(row[2])
            if row[2] is not None
            else None
        ),
        "gift_amount": (
            str(row[3])
            if row[3] is not None
            else None
        ),
        "calendar_year": row[4],
        "status": row[5],
        "exception_reason": row[6]
    }


def create_import(event):

    user_id = get_user_id(event)

    if not user_id:
        return forbidden({
            "error": "Unable to identify authenticated user"
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO payment_imports (
                    created_by,
                    status
                )
                VALUES (%s, 'IN_PROGRESS')
                RETURNING
                    id,
                    created_at,
                    created_by,
                    status;
                """,
                (user_id,)
            )

            row = cur.fetchone()

        conn.commit()

        return created({
            "import": import_from_row(row)
        })

    finally:
        conn.close()


def get_import(event):

    path_parameters = (
        event.get("pathParameters") or {}
    )

    import_id = path_parameters.get("id")

    if not import_id:
        return bad_request({
            "error": "Import id is required"
        })

    try:
        import_id = int(import_id)
    except ValueError:
        return bad_request({
            "error": "Import id must be a number"
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    created_at,
                    created_by,
                    status

                FROM payment_imports

                WHERE id = %s;
                """,
                (import_id,)
            )

            import_row = cur.fetchone()

            if import_row is None:
                return not_found({
                    "error": "Payment import not found"
                })

            cur.execute(
                """
                SELECT
                    id,
                    statement_reference,
                    payment_date,
                    statement_amount,
                    statement_type,
                    description,
                    action

                FROM payment_import_lines

                WHERE import_id = %s

                ORDER BY id;
                """,
                (import_id,)
            )

            line_rows = cur.fetchall()

            lines = []

            for line_row in line_rows:

                line = line_from_row(line_row)

                cur.execute(
                    """
                    SELECT
                        id,
                        member_id,
                        subscription_amount,
                        gift_amount,
                        calendar_year,
                        status,
                        exception_reason

                    FROM payment_import_items

                    WHERE import_line_id = %s

                    ORDER BY id;
                    """,
                    (line["id"],)
                )

                item_rows = cur.fetchall()

                line["items"] = [
                    item_from_row(row)
                    for row in item_rows
                ]

                lines.append(line)

            return success({
                "import": import_from_row(import_row),
                "lines": lines
            })

    finally:
        conn.close()


def create_import_lines(event):

    path_parameters = (
        event.get("pathParameters") or {}
    )

    import_id = path_parameters.get("id")

    if not import_id:
        return bad_request({
            "error": "Import id is required"
        })

    try:
        import_id = int(import_id)
    except ValueError:
        return bad_request({
            "error": "Import id must be a number"
        })

    body = event.get("body")

    if not body:
        return bad_request({
            "error": "Request body is required"
        })

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return bad_request({
            "error": "Request body must be valid JSON"
        })

    lines = payload.get("lines")

    if not isinstance(lines, list) or not lines:
        return bad_request({
            "error": "lines must be a non-empty list"
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    status

                FROM payment_imports

                WHERE id = %s;
                """,
                (import_id,)
            )

            import_row = cur.fetchone()

            if import_row is None:
                return not_found({
                    "error": "Payment import not found"
                })

            if import_row[1] != "IN_PROGRESS":
                return bad_request({
                    "error": "Payment import is not open"
                })

            created_lines = []

            for line in lines:

                statement_reference = line.get(
                    "statement_reference"
                )

                payment_date = line.get(
                    "payment_date"
                )

                statement_amount = line.get(
                    "statement_amount"
                )

                description = line.get(
                    "description"
                )

                statement_type = line.get(
                    "statement_type"
                )

                action = line.get("action")

                if not statement_reference:
                    return bad_request({
                        "error": "statement_reference is required"
                    })

                if not payment_date:
                    return bad_request({
                        "error": "payment_date is required"
                    })

                if statement_amount is None:
                    return bad_request({
                        "error": "statement_amount is required"
                    })

                if description is None:
                    return bad_request({
                        "error": "description is required"
                    })

                if action not in ("IMPORT", "IGNORE"):
                    return bad_request({
                        "error": (
                            "action must be IMPORT or IGNORE"
                        )
                    })

                try:
                    statement_amount = Decimal(
                        str(statement_amount)
                    )
                except (
                    InvalidOperation,
                    TypeError,
                    ValueError
                ):
                    return bad_request({
                        "error": (
                            "statement_amount must be a number"
                        )
                    })

                cur.execute(
                    """
                    INSERT INTO payment_import_lines (
                        import_id,
                        statement_reference,
                        payment_date,
                        statement_amount,
                        statement_type,
                        description,
                        action
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING
                        id,
                        statement_reference,
                        payment_date,
                        statement_amount,
                        statement_type,
                        description,
                        action;
                    """,
                    (
                        import_id,
                        statement_reference,
                        payment_date,
                        statement_amount,
                        statement_type,
                        description,
                        action
                    )
                )

                row = cur.fetchone()

                created_lines.append(
                    line_from_row(row)
                )

        conn.commit()

        return created({
            "lines": created_lines
        })

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def create_import_item(event):

    path_parameters = (
        event.get("pathParameters") or {}
    )

    line_id = path_parameters.get("id")

    if not line_id:
        return bad_request({
            "error": "Import line id is required"
        })

    try:
        line_id = int(line_id)
    except ValueError:
        return bad_request({
            "error": "Import line id must be a number"
        })

    body = event.get("body")

    if not body:
        return bad_request({
            "error": "Request body is required"
        })

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return bad_request({
            "error": "Request body must be valid JSON"
        })

    member_id = payload.get("member_id")
    subscription_amount = payload.get("subscription_amount")
    gift_amount = payload.get("gift_amount")
    calendar_year = payload.get("calendar_year")

    if member_id is None:
        return bad_request({
            "error": "member_id is required"
        })

    try:
        member_id = int(member_id)
    except (TypeError, ValueError):
        return bad_request({
            "error": "member_id must be a number"
        })

    if subscription_amount is None:
        subscription_amount = Decimal("0.00")
    else:
        try:
            subscription_amount = Decimal(
                str(subscription_amount)
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError
        ):
            return bad_request({
                "error": (
                    "subscription_amount must be a number"
                )
            })

    if gift_amount is None:
        gift_amount = Decimal("0.00")
    else:
        try:
            gift_amount = Decimal(
                str(gift_amount)
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError
        ):
            return bad_request({
                "error": "gift_amount must be a number"
            })

    if subscription_amount == 0 and gift_amount == 0:
        return bad_request({
            "error": "At least one payment amount is required"
        })

    if calendar_year is None:
        return bad_request({
            "error": "calendar_year is required"
        })

    try:
        calendar_year = int(calendar_year)
    except (TypeError, ValueError):
        return bad_request({
            "error": "calendar_year must be a number"
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    import_id,
                    statement_amount,
                    action

                FROM payment_import_lines

                WHERE id = %s;
                """,
                (line_id,)
            )

            line_row = cur.fetchone()

            if line_row is None:
                return not_found({
                    "error": "Payment import line not found"
                })

            statement_amount = Decimal(
                str(line_row[2])
            )

            import_id = line_row[1]
            action = line_row[3]

            if action != "IMPORT":
                return bad_request({
                    "error": (
                        "Cannot allocate a line marked IGNORE"
                    )
                })

            cur.execute(
                """
                SELECT status

                FROM payment_imports

                WHERE id = %s;
                """,
                (import_id,)
            )

            import_row = cur.fetchone()

            if import_row is None:
                return not_found({
                    "error": "Payment import not found"
                })

            if import_row[0] != "IN_PROGRESS":
                return bad_request({
                    "error": "Payment import is not open"
                })

            cur.execute(
                """
                SELECT id

                FROM members

                WHERE id = %s;
                """,
                (member_id,)
            )

            member_row = cur.fetchone()

            if member_row is None:
                return bad_request({
                    "error": "Member not found"
                })

            cur.execute(
                """
                SELECT
                    COALESCE(
                        SUM(
                            COALESCE(subscription_amount, 0)
                            +
                            COALESCE(gift_amount, 0)
                        ),
                        0
                    )

                FROM payment_import_items

                WHERE import_line_id = %s
                AND status <> 'RESOLVED_EXTERNALLY';
                """,
                (line_id,)
            )

            allocated_amount = Decimal(
                str(cur.fetchone()[0])
            )

            new_amount = (
                subscription_amount
                + gift_amount
            )

            new_total = (
                allocated_amount
                + new_amount
            )

            if new_total > statement_amount:
                remaining = (
                    statement_amount
                    - allocated_amount
                )

                return bad_request({
                    "error": (
                        "Allocation exceeds "
                        "remaining statement amount"
                    ),
                    "statement_amount": str(
                        statement_amount
                    ),
                    "already_allocated": str(
                        allocated_amount
                    ),
                    "remaining": str(
                        remaining
                    ),
                    "requested": str(
                        new_amount
                    )
                })

            cur.execute(
                """
                INSERT INTO payment_import_items (
                    import_line_id,
                    member_id,
                    subscription_amount,
                    gift_amount,
                    calendar_year,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'PENDING'
                )
                RETURNING
                    id,
                    member_id,
                    subscription_amount,
                    gift_amount,
                    calendar_year,
                    status,
                    exception_reason;
                """,
                (
                    line_id,
                    member_id,
                    subscription_amount,
                    gift_amount,
                    calendar_year
                )
            )

            row = cur.fetchone()

        conn.commit()

        return created({
            "item": item_from_row(row),
            "statement_amount": format(
                statement_amount,
                ".2f"
            ),
            "allocated_amount": format(
                new_total,
                ".2f"
            ),
            "remaining_amount": format(
                statement_amount - new_total,
                ".2f"
            )
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

    path_parameters = (
        event.get("pathParameters") or {}
    )

    route_key = event.get("routeKey")

    # ---------------------------------------------------------
    # Create payment import
    # POST /payment-imports
    # ---------------------------------------------------------

    if (
        http_method == "POST"
        and not path_parameters
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to create payment imports"
                )
            })

        return create_import(event)

    # ---------------------------------------------------------
    # Get payment import
    # GET /payment-imports/{id}
    # ---------------------------------------------------------

    if (
        http_method == "GET"
        and path_parameters.get("id")
    ):
        return get_import(event)

    # ---------------------------------------------------------
    # Create payment import item
    # POST /payment-import-lines/{id}/items
    # ---------------------------------------------------------

    if (
        http_method == "POST"
        and route_key
        == "POST /payment-import-lines/{id}/items"
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to allocate payment import lines"
                )
            })

        return create_import_item(event)

    # ---------------------------------------------------------
    # Add payment import lines
    # POST /payment-imports/{id}/lines
    # ---------------------------------------------------------

    if (
        http_method == "POST"
        and path_parameters.get("id")
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to add payment import lines"
                )
            })

        return create_import_lines(event)

    return bad_request({
        "error": "Unsupported request"
    })
