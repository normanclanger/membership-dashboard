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
    return "LOCAL-TEST-USER"
#    claims = get_claims(event)

#    return claims.get("sub")


def can_write_imports(event):
    return True

#    groups = get_user_groups(event)

#    return bool(
#        groups.intersection(ALLOWED_WRITE_GROUPS)
#    )

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

    import_id = path_parameters.get("import_id")

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

    line_id = path_parameters.get("line_id")

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


def amend_import_item(event):

    path_parameters = (
        event.get("pathParameters") or {}
    )

    item_id = path_parameters.get("item_id")

    if not item_id:
        return bad_request({
            "error": "Import item id is required"
        })

    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return bad_request({
            "error": "Import item id must be a number"
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

    if not isinstance(payload, dict):
        return bad_request({
            "error": "Request body must be an object"
        })

    allowed_fields = {
        "member_id",
        "subscription_amount",
        "gift_amount",
        "calendar_year",
        "status",
        "exception_reason"
    }

    unknown_fields = set(payload) - allowed_fields

    if unknown_fields:
        return bad_request({
            "error": "Unsupported field(s)",
            "fields": sorted(unknown_fields)
        })

    if not payload:
        return bad_request({
            "error": "At least one field is required"
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # Get the existing item and its statement line
            # -------------------------------------------------

            cur.execute(
                """
                SELECT
                    i.id,
                    i.import_line_id,
                    i.member_id,
                    i.subscription_amount,
                    i.gift_amount,
                    i.calendar_year,
                    i.status,
                    i.exception_reason,
                    l.statement_amount,
                    l.action,
                    l.import_id

                FROM payment_import_items i

                JOIN payment_import_lines l
                    ON l.id = i.import_line_id

                WHERE i.id = %s;
                """,
                (item_id,)
            )

            row = cur.fetchone()

            if row is None:
                return not_found({
                    "error": "Payment import item not found"
                })

            (
                current_id,
                line_id,
                current_member_id,
                current_subscription_amount,
                current_gift_amount,
                current_calendar_year,
                current_status,
                current_exception_reason,
                statement_amount,
                line_action,
                import_id
            ) = row

            # -------------------------------------------------
            # Check import status
            # -------------------------------------------------

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

            # -------------------------------------------------
            # Check statement-line action
            # -------------------------------------------------

            if line_action != "IMPORT":
                return bad_request({
                    "error": (
                        "Cannot amend an allocation for "
                        "a line marked IGNORE"
                    )
                })

            # -------------------------------------------------
            # Check current item status
            # -------------------------------------------------

            if current_status in (
                "COMMITTED",
                "RESOLVED_EXTERNALLY"
            ):
                return bad_request({
                    "error": (
                        "This payment import item "
                        "cannot be amended"
                    )
                })

            # -------------------------------------------------
            # Determine proposed values
            # -------------------------------------------------

            proposed_member_id = current_member_id

            if "member_id" in payload:
                proposed_member_id = payload["member_id"]

                if proposed_member_id is not None:
                    try:
                        proposed_member_id = int(
                            proposed_member_id
                        )
                    except (TypeError, ValueError):
                        return bad_request({
                            "error": "member_id must be a number"
                        })

                    cur.execute(
                        """
                        SELECT id

                        FROM members

                        WHERE id = %s;
                        """,
                        (proposed_member_id,)
                    )

                    if cur.fetchone() is None:
                        return bad_request({
                            "error": "Member not found"
                        })

            proposed_subscription_amount = (
                current_subscription_amount
            )

            if "subscription_amount" in payload:

                if payload["subscription_amount"] is None:
                    proposed_subscription_amount = Decimal(
                        "0.00"
                    )
                else:
                    try:
                        proposed_subscription_amount = Decimal(
                            str(
                                payload[
                                    "subscription_amount"
                                ]
                            )
                        )
                    except (
                        InvalidOperation,
                        TypeError,
                        ValueError
                    ):
                        return bad_request({
                            "error": (
                                "subscription_amount "
                                "must be a number"
                            )
                        })

            proposed_gift_amount = current_gift_amount

            if "gift_amount" in payload:

                if payload["gift_amount"] is None:
                    proposed_gift_amount = Decimal(
                        "0.00"
                    )
                else:
                    try:
                        proposed_gift_amount = Decimal(
                            str(
                                payload["gift_amount"]
                            )
                        )
                    except (
                        InvalidOperation,
                        TypeError,
                        ValueError
                    ):
                        return bad_request({
                            "error": (
                                "gift_amount must be a number"
                            )
                        })

            if proposed_subscription_amount is None:
                proposed_subscription_amount = Decimal(
                    "0.00"
                )

            if proposed_gift_amount is None:
                proposed_gift_amount = Decimal(
                    "0.00"
                )

            if (
                proposed_subscription_amount == 0
                and proposed_gift_amount == 0
            ):
                return bad_request({
                    "error": (
                        "At least one payment amount "
                        "is required"
                    )
                })

            proposed_calendar_year = current_calendar_year

            if "calendar_year" in payload:

                if payload["calendar_year"] is None:
                    return bad_request({
                        "error": "calendar_year is required"
                    })

                try:
                    proposed_calendar_year = int(
                        payload["calendar_year"]
                    )
                except (TypeError, ValueError):
                    return bad_request({
                        "error": (
                            "calendar_year must be a number"
                        )
                    })

            proposed_status = current_status

            if "status" in payload:
                proposed_status = payload["status"]

            proposed_exception_reason = (
                current_exception_reason
            )

            if "exception_reason" in payload:
                proposed_exception_reason = (
                    payload["exception_reason"]
                )

            # -------------------------------------------------
            # Validate status transitions
            # -------------------------------------------------

            valid_transitions = {
                "PENDING": {
                    "PENDING",
                    "READY",
                    "EXCEPTION"
                },
                "EXCEPTION": {
                    "EXCEPTION",
                    "PENDING",
                    "RESOLVED_EXTERNALLY"
                },
                "READY": {
                    "READY",
                    "EXCEPTION"
                }
            }

            allowed_statuses = valid_transitions.get(
                current_status,
                set()
            )

            if proposed_status not in allowed_statuses:
                return bad_request({
                    "error": (
                        f"Invalid status transition "
                        f"from {current_status} "
                        f"to {proposed_status}"
                    )
                })

            # -------------------------------------------------
            # EXCEPTION requires a reason
            # -------------------------------------------------

            if proposed_status == "EXCEPTION":

                if not proposed_exception_reason:
                    return bad_request({
                        "error": (
                            "exception_reason is required "
                            "for EXCEPTION status"
                        )
                    })

            # -------------------------------------------------
            # RESOLVED_EXTERNALLY
            # -------------------------------------------------

            if proposed_status == "RESOLVED_EXTERNALLY":

                if current_status != "EXCEPTION":
                    return bad_request({
                        "error": (
                            "Only EXCEPTION items can be "
                            "marked RESOLVED_EXTERNALLY"
                        )
                    })

            # -------------------------------------------------
            # Calculate proposed reconciliation
            #
            # IMPORTANT:
            # Exclude this item's current allocation,
            # then add its proposed allocation.
            # -------------------------------------------------

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
                AND id <> %s
                AND status <> 'RESOLVED_EXTERNALLY';
                """,
                (
                    line_id,
                    item_id
                )
            )

            other_allocations = Decimal(
                str(cur.fetchone()[0])
            )

            proposed_amount = (
                proposed_subscription_amount
                + proposed_gift_amount
            )

            proposed_total = (
                other_allocations
                + proposed_amount
            )

            statement_amount = Decimal(
                str(statement_amount)
            )

            # -------------------------------------------------
            # READY requires exact reconciliation
            # -------------------------------------------------

            if proposed_status == "READY":

                if proposed_total != statement_amount:
                    return bad_request({
                        "error": (
                            "Statement line is not "
                            "fully reconciled"
                        ),
                        "statement_amount": format(
                            statement_amount,
                            ".2f"
                        ),
                        "allocated_amount": format(
                            proposed_total,
                            ".2f"
                        ),
                        "remaining_amount": format(
                            statement_amount
                            - proposed_total,
                            ".2f"
                        )
                    })

            # -------------------------------------------------
            # Prevent positive over-allocation.
            #
            # Negative allocations are allowed.
            # -------------------------------------------------

            if proposed_total > statement_amount:
                return bad_request({
                    "error": (
                        "Allocation exceeds "
                        "statement amount"
                    ),
                    "statement_amount": format(
                        statement_amount,
                        ".2f"
                    ),
                    "allocated_amount": format(
                        proposed_total,
                        ".2f"
                    ),
                    "remaining_amount": format(
                        statement_amount
                        - proposed_total,
                        ".2f"
                    )
                })

            # -------------------------------------------------
            # Update the existing item
            # -------------------------------------------------

            cur.execute(
                """
                UPDATE payment_import_items

                SET
                    member_id = %s,
                    subscription_amount = %s,
                    gift_amount = %s,
                    calendar_year = %s,
                    status = %s,
                    exception_reason = %s,
                    updated_at = now()

                WHERE id = %s

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
                    proposed_member_id,
                    proposed_subscription_amount,
                    proposed_gift_amount,
                    proposed_calendar_year,
                    proposed_status,
                    proposed_exception_reason,
                    item_id
                )
            )

            updated_row = cur.fetchone()

        conn.commit()

        return success({
            "item": item_from_row(updated_row),
            "statement_amount": format(
                statement_amount,
                ".2f"
            ),
            "allocated_amount": format(
                proposed_total,
                ".2f"
            ),
            "remaining_amount": format(
                statement_amount - proposed_total,
                ".2f"
            )
        })

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def delete_import_item(event):

    path_parameters = (
        event.get("pathParameters") or {}
    )

    item_id = path_parameters.get("item_id")

    if not item_id:
        return bad_request({
            "error": "Import item id is required"
        })

    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return bad_request({
            "error": "Import item id must be a number"
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # Get the item and its statement line
            # -------------------------------------------------

            cur.execute(
                """
                SELECT
                    i.id,
                    i.import_line_id,
                    i.status,
                    l.statement_amount,
                    l.action,
                    l.import_id

                FROM payment_import_items i

                JOIN payment_import_lines l
                    ON l.id = i.import_line_id

                WHERE i.id = %s;
                """,
                (item_id,)
            )

            row = cur.fetchone()

            if row is None:
                return not_found({
                    "error": "Payment import item not found"
                })

            (
                current_item_id,
                line_id,
                current_status,
                statement_amount,
                line_action,
                import_id
            ) = row

            # -------------------------------------------------
            # Check import status
            # -------------------------------------------------

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

            # -------------------------------------------------
            # Cannot delete final items
            # -------------------------------------------------

            if current_status in (
                "COMMITTED",
                "RESOLVED_EXTERNALLY"
            ):
                return bad_request({
                    "error": (
                        "This payment import item "
                        "cannot be deleted"
                    )
                })

            # -------------------------------------------------
            # Delete the item
            # -------------------------------------------------

            cur.execute(
                """
                DELETE FROM payment_import_items

                WHERE id = %s

                RETURNING
                    id;
                """,
                (item_id,)
            )

            deleted_row = cur.fetchone()

            if deleted_row is None:
                return not_found({
                    "error": "Payment import item not found"
                })

            # -------------------------------------------------
            # Recalculate the statement line
            #
            # RESOLVED_EXTERNALLY items are deliberately
            # excluded from reconciliation.
            # -------------------------------------------------

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

            statement_amount = Decimal(
                str(statement_amount)
            )

            # -------------------------------------------------
            # If the line is no longer fully reconciled,
            # invalidate all remaining READY items.
            # -------------------------------------------------

            ready_items_reset = 0

            if allocated_amount != statement_amount:

                cur.execute(
                    """
                    UPDATE payment_import_items

                    SET
                        status = 'PENDING',
                        updated_at = now()

                    WHERE import_line_id = %s
                    AND status = 'READY';
                    """,
                    (line_id,)
                )

                ready_items_reset = cur.rowcount

            conn.commit()

            return success({
                "deleted_item_id": deleted_row[0],
                "statement_line_id": line_id,
                "statement_amount": format(
                    statement_amount,
                    ".2f"
                ),
                "allocated_amount": format(
                    allocated_amount,
                    ".2f"
                ),
                "remaining_amount": format(
                    statement_amount - allocated_amount,
                    ".2f"
                ),
                "ready_items_reset": ready_items_reset
            })

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def amend_import_line(event):

    path_parameters = (
        event.get("pathParameters") or {}
    )

    line_id = path_parameters.get("line_id")

    if not line_id:
        return bad_request({
            "error": "Import line id is required"
        })

    try:
        line_id = int(line_id)
    except (TypeError, ValueError):
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

    if not isinstance(payload, dict):
        return bad_request({
            "error": "Request body must be an object"
        })

    # This endpoint changes only the action.
    if set(payload.keys()) != {"action"}:
        return bad_request({
            "error": (
                "Only action may be changed"
            )
        })

    action = payload.get("action")

    if action not in ("IMPORT", "IGNORE"):
        return bad_request({
            "error": (
                "action must be IMPORT or IGNORE"
            )
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # ---------------------------------------------
            # Get the statement line
            # ---------------------------------------------

            cur.execute(
                """
                SELECT
                    id,
                    import_id,
                    statement_reference,
                    payment_date,
                    statement_amount,
                    statement_type,
                    description,
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

            import_id = line_row[1]
            current_action = line_row[7]

            # ---------------------------------------------
            # Check the import is still open
            # ---------------------------------------------

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

            # ---------------------------------------------
            # IMPORT -> IGNORE
            #
            # This is only allowed when the line has
            # no allocation items at all.
            # ---------------------------------------------

            if (
                current_action == "IMPORT"
                and action == "IGNORE"
            ):

                cur.execute(
                    """
                    SELECT COUNT(*)

                    FROM payment_import_items

                    WHERE import_line_id = %s;
                    """,
                    (line_id,)
                )

                item_count = cur.fetchone()[0]

                if item_count > 0:
                    return bad_request({
                        "error": (
                            "Cannot change line to IGNORE "
                            "while allocation items exist"
                        ),
                        "item_count": item_count
                    })

            # ---------------------------------------------
            # Update only the action
            # ---------------------------------------------

            cur.execute(
                """
                UPDATE payment_import_lines

                SET action = %s

                WHERE id = %s

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
                    action,
                    line_id
                )
            )

            updated_row = cur.fetchone()

        conn.commit()

        return success({
            "line": line_from_row(updated_row)
        })

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def commit_import_line(event):

    # ---------------------------------------------------------
    # Identify authenticated user
    # ---------------------------------------------------------

    user_id = get_user_id(event)

    if not user_id:
        return forbidden({
            "error": "Unable to identify authenticated user"
        })

    # ---------------------------------------------------------
    # Get line ID
    # ---------------------------------------------------------

    path_parameters = (
        event.get("pathParameters") or {}
    )

    line_id = path_parameters.get("line_id")

    if not line_id:
        return bad_request({
            "error": "Payment import line id is required"
        })

    try:
        line_id = int(line_id)
    except (TypeError, ValueError):
        return bad_request({
            "error": (
                "Payment import line id must be a number"
            )
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # Get statement line
            # -------------------------------------------------

            cur.execute(
                """
                SELECT
                    l.id,
                    l.import_id,
                    l.statement_reference,
                    l.payment_date,
                    l.statement_amount,
                    l.action,
                    l.status,
                    i.status

                FROM payment_import_lines l

                JOIN payment_imports i
                    ON i.id = l.import_id

                WHERE l.id = %s;
                """,
                (line_id,)
            )

            line_row = cur.fetchone()

            if line_row is None:
                return not_found({
                    "error": "Payment import line not found"
                })

            (
                current_line_id,
                import_id,
                statement_reference,
                payment_date,
                statement_amount,
                line_action,
                line_status,
                import_status
            ) = line_row

            # -------------------------------------------------
            # Check parent import
            # -------------------------------------------------

            if import_status != "IN_PROGRESS":
                return bad_request({
                    "error": "Payment import is not open"
                })

            # -------------------------------------------------
            # Only IMPORT lines can be committed
            # -------------------------------------------------

            if line_action != "IMPORT":
                return bad_request({
                    "error": (
                        "Only lines marked IMPORT "
                        "can be committed"
                    )
                })

            # -------------------------------------------------
            # Prevent double commit
            # -------------------------------------------------

            if line_status == "COMMITTED":
                return bad_request({
                    "error": (
                        "Payment import line "
                        "has already been committed"
                    )
                })

            # -------------------------------------------------
            # Get all items for this line
            # -------------------------------------------------

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
                (line_id,)
            )

            item_rows = cur.fetchall()

            if not item_rows:
                return bad_request({
                    "error": (
                        "Cannot commit a statement line "
                        "with no allocation items"
                    )
                })

            # -------------------------------------------------
            # Check item statuses
            # -------------------------------------------------

            blocking_items = []

            ready_items = []
            externally_resolved_items = []

            for row in item_rows:

                item = item_from_row(row)

                if item["status"] == "READY":
                    ready_items.append(item)

                elif (
                    item["status"]
                    == "RESOLVED_EXTERNALLY"
                ):
                    externally_resolved_items.append(item)

                else:
                    blocking_items.append({
                        "id": item["id"],
                        "status": item["status"],
                        "exception_reason": (
                            item["exception_reason"]
                        )
                    })

            if blocking_items:
                return bad_request({
                    "error": (
                        "Statement line contains items "
                        "that are not ready to commit"
                    ),
                    "items": blocking_items
                })

            # -------------------------------------------------
            # Reconcile READY items.
            #
            # RESOLVED_EXTERNALLY items are excluded.
            # -------------------------------------------------

            allocated_amount = Decimal("0.00")

            for item in ready_items:

                subscription_amount = Decimal(
                    item["subscription_amount"]
                    or "0.00"
                )

                gift_amount = Decimal(
                    item["gift_amount"]
                    or "0.00"
                )

                allocated_amount += (
                    subscription_amount
                    + gift_amount
                )

            statement_amount = Decimal(
                str(statement_amount)
            )

            if allocated_amount != statement_amount:

                return bad_request({
                    "error": (
                        "Statement line is not fully "
                        "reconciled"
                    ),
                    "statement_amount": format(
                        statement_amount,
                        ".2f"
                    ),
                    "allocated_amount": format(
                        allocated_amount,
                        ".2f"
                    ),
                    "remaining_amount": format(
                        statement_amount
                        - allocated_amount,
                        ".2f"
                    )
                })

            # -------------------------------------------------
            # Create permanent payment records
            # -------------------------------------------------

            created_payments = []

            for item in ready_items:

                subscription_amount = Decimal(
                    item["subscription_amount"]
                    or "0.00"
                )

                gift_amount = Decimal(
                    item["gift_amount"]
                    or "0.00"
                )

                cur.execute(
                    """
                    INSERT INTO payments (
                        payment_date,
                        statement_reference,
                        member_id,
                        subscription_amount,
                        gift_amount,
                        calendar_year,
                        import_item_id,
                        created_by
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING
                        id,
                        payment_date,
                        statement_reference,
                        member_id,
                        subscription_amount,
                        gift_amount,
                        calendar_year,
                        import_item_id;
                    """,
                    (
                        payment_date,
                        statement_reference,
                        item["member_id"],
                        subscription_amount,
                        gift_amount,
                        item["calendar_year"],
                        item["id"],
                        user_id
                    )
                )

                payment_row = cur.fetchone()

                created_payments.append({
                    "id": payment_row[0],
                    "payment_date": (
                        payment_row[1].isoformat()
                    ),
                    "statement_reference": (
                        payment_row[2]
                    ),
                    "member_id": payment_row[3],
                    "subscription_amount": str(
                        payment_row[4]
                    ),
                    "gift_amount": str(
                        payment_row[5]
                    ),
                    "calendar_year": payment_row[6],
                    "import_item_id": payment_row[7]
                })

            # -------------------------------------------------
            # Mark READY items as COMMITTED
            # -------------------------------------------------

            ready_item_ids = [
                item["id"]
                for item in ready_items
            ]

            if ready_item_ids:

                cur.execute(
                    """
                    UPDATE payment_import_items

                    SET
                        status = 'COMMITTED',
                        updated_at = now()

                    WHERE id = ANY(%s);
                    """,
                    (ready_item_ids,)
                )

            # -------------------------------------------------
            # Mark statement line as COMMITTED
            # -------------------------------------------------

            cur.execute(
                """
                UPDATE payment_import_lines

                SET
                    status = 'COMMITTED',
                    committed_at = now(),
                    committed_by = %s

                WHERE id = %s

                RETURNING
                    id,
                    status,
                    committed_at,
                    committed_by;
                """,
                (
                    user_id,
                    line_id
                )
            )

            committed_line = cur.fetchone()

        conn.commit()

        return success({
            "line": {
                "id": committed_line[0],
                "status": committed_line[1],
                "committed_at": (
                    committed_line[2].isoformat()
                ),
                "committed_by": committed_line[3]
            },
            "statement_amount": format(
                statement_amount,
                ".2f"
            ),
            "allocated_amount": format(
                allocated_amount,
                ".2f"
            ),
            "payments_created": created_payments,
            "externally_resolved_item_ids": [
                item["id"]
                for item in externally_resolved_items
            ]
        })

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def complete_import(event):

    # ---------------------------------------------------------
    # Get import ID
    # ---------------------------------------------------------

    path_parameters = (
        event.get("pathParameters") or {}
    )

    import_id = path_parameters.get("import_id")

    if not import_id:
        return bad_request({
            "error": "Import id is required"
        })

    try:
        import_id = int(import_id)
    except (TypeError, ValueError):
        return bad_request({
            "error": "Import id must be a number"
        })

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # Get import
            # -------------------------------------------------

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

            if import_row[3] != "IN_PROGRESS":
                return bad_request({
                    "error": "Payment import is not open"
                })

            # -------------------------------------------------
            # Find unfinished IMPORT lines
            # -------------------------------------------------

            cur.execute(
                """
                SELECT
                    id,
                    status

                FROM payment_import_lines

                WHERE import_id = %s
                AND action = 'IMPORT'
                AND status <> 'COMMITTED'

                ORDER BY id;
                """,
                (import_id,)
            )

            unfinished_lines = cur.fetchall()

            if unfinished_lines:

                return bad_request({
                    "error": (
                        "Payment import contains "
                        "uncommitted lines"
                    ),
                    "lines": [
                        {
                            "id": row[0],
                            "status": row[1]
                        }
                        for row in unfinished_lines
                    ]
                })

            # -------------------------------------------------
            # Mark import as COMPLETE
            # -------------------------------------------------

            cur.execute(
                """
                UPDATE payment_imports

                SET status = 'COMPLETE'

                WHERE id = %s

                RETURNING
                    id,
                    created_at,
                    created_by,
                    status;
                """,
                (import_id,)
            )

            completed_row = cur.fetchone()

        conn.commit()

        return success({
            "import": import_from_row(completed_row)
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
    print("DEBUG METHOD:", http_method)
    print("DEBUG ROUTE KEY:", route_key)
    print("DEBUG PATH PARAMETERS:", path_parameters)

    # ---------------------------------------------------------
    # Commit payment import line
    # POST /payment-import-lines/{line_id}/commit
    # ---------------------------------------------------------

    if (
        http_method == "POST"
        and route_key
        == "POST /api/payment-import-lines/{line_id}/commit"
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to commit payment import lines"
                )
            })

        return commit_import_line(event)	


    # ---------------------------------------------------------
    # Delete payment import item
    # DELETE /payment-import-items/{item_id}
    # ---------------------------------------------------------

    if (
        http_method == "DELETE"
        and route_key
        == "DELETE /api/payment-import-items/{item_id}"
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to delete payment import items"
                )
            })

        return delete_import_item(event)

    # ---------------------------------------------------------
    # Change payment import line action
    # PATCH /payment-import-lines/{line_id}
    # ---------------------------------------------------------

    if (
        http_method == "PATCH"
        and route_key
        == "PATCH /api/payment-import-lines/{line_id}"
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to amend payment import lines"
                )
            })

        return amend_import_line(event)

    # ---------------------------------------------------------
    # Amend payment import item
    # PATCH /payment-import-items/{item_id}
    # ---------------------------------------------------------

    if (
        http_method == "PATCH"
        and route_key
        == "PATCH /api/payment-import-items/{item_id}"
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to amend payment import items"
                )
            })

        return amend_import_item(event)

    # ---------------------------------------------------------
    # Complete payment import
    # POST /api/payment-imports/{import_id}/complete
    # ---------------------------------------------------------

    if (
        http_method == "POST"
        and route_key
        == "POST /api/payment-imports/{import_id}/complete"
    ):
        if not can_write_imports(event):
            return forbidden({
                "error": (
                    "You do not have permission "
                    "to complete payment imports"
                )
            })

        return complete_import(event)

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
    # GET /payment-imports/{import_id}
    # ---------------------------------------------------------

    if (
        http_method == "GET"
        and path_parameters.get("import_id")
    ):
        return get_import(event)

    # ---------------------------------------------------------
    # Create payment import item
    # POST /payment-import-lines/{line_id}/items
    # ---------------------------------------------------------

    if (
        http_method == "POST"
        and route_key
        == "POST /api/payment-import-lines/{line_id}/items"
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
