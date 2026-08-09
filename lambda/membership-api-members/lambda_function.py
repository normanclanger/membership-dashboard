import json

from database import get_connection
from responses import (
    success,
    created,
    bad_request,
    not_found,
    conflict
)


def member_from_row(row):
    return {
        "id": row[0],
        "membership_number": row[1],
        "first_name": row[2],
        "surname": row[3],
        "tower_id": row[4],
        "date_of_birth": row[5].isoformat() if row[5] else None,
        "membership_class_id": row[6],
        "membership_status_id": row[7],
        "full_member_type_id": row[8]
    }


def lambda_handler(event, context):
    http_method = event.get("requestContext", {}).get("http", {}).get("method")

    # ---------------------------------------------------------
    # POST /api/members
    # ---------------------------------------------------------
    if http_method == "POST":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return bad_request({
                "error": "Request body must contain valid JSON"
            })

        required_fields = [
            "membership_number",
            "first_name",
            "surname",
            "tower_id"
        ]

        missing = [
            field for field in required_fields
            if field not in body or body[field] in (None, "")
        ]

        if missing:
            return bad_request({
                "error": "Missing required fields",
                "fields": missing
            })

        conn = get_connection()

        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO members (
                            membership_number,
                            first_name,
                            surname,
                            tower_id,
                            date_of_birth,
                            membership_class_id,
                            membership_status_id,
                            full_member_type_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING
                            id,
                            membership_number,
                            first_name,
                            surname,
                            tower_id,
                            date_of_birth,
                            membership_class_id,
                            membership_status_id,
                            full_member_type_id;
                        """,
                        (
                            body["membership_number"],
                            body["first_name"],
                            body["surname"],
                            body["tower_id"],
                            body.get("date_of_birth"),
                            body.get("membership_class_id"),
                            body.get("membership_status_id"),
                            body.get("full_member_type_id")
                        )
                    )


                    row = cur.fetchone()
                    conn.commit()

                except Exception as exc:
                    conn.rollback()

                    # PostgreSQL unique constraint violation
                    if getattr(exc, "sqlstate", None) == "23505":
                        return conflict({
                            "error": "Membership number already exists"
                        })

                    # PostgreSQL foreign key violation
                    if getattr(exc, "sqlstate", None) == "23503":
                        return bad_request({
                            "error": "One or more referenced records do not exist"
                        })

                    raise


        finally:
            conn.close()

        return created({
            "member": member_from_row(row)
        })

    # ---------------------------------------------------------
    # GET /api/members/{id}
    # ---------------------------------------------------------
    path_parameters = event.get("pathParameters") or {}
    member_id = path_parameters.get("id")

    query_parameters = event.get("queryStringParameters") or {}
    search = query_parameters.get("search")

    conn = get_connection()


    try:
        with conn.cursor() as cur:

            if member_id:
                cur.execute(
                    """
                    SELECT
                        id,
                        membership_number,
                        first_name,
                        surname,
                        tower_id,
                        date_of_birth,
                        membership_class_id,
                        membership_status_id,
                        full_member_type_id
                    FROM members
                    WHERE id = %s;
                    """,
                    (member_id,)
                )

                row = cur.fetchone()

                if row is None:
                    return not_found({
                        "error": "Member not found"
                    })

                return success({
                    "member": member_from_row(row)
                })

            if search:
                cur.execute(
                    """
                    SELECT
                        id,
                        membership_number,
                        first_name,
                        surname,
                        tower_id,
                        date_of_birth,
                        membership_class_id,
                        membership_status_id,
                        full_member_type_id
                    FROM members
                    WHERE membership_number ILIKE %s
                       OR first_name ILIKE %s
                       OR surname ILIKE %s
                    ORDER BY surname, first_name;
                    """,
                    (f"%{search}%", f"%{search}%", f"%{search}%")
                )
            else:
                cur.execute(
                    """
                    SELECT
                        id,
                        membership_number,
                        first_name,
                        surname,
                        tower_id,
                        date_of_birth,
                        membership_class_id,
                        membership_status_id,
                        full_member_type_id
                    FROM members
                    ORDER BY surname, first_name;
                    """
                )

            rows = cur.fetchall()

    finally:
        conn.close()

    return success({
        "members": [member_from_row(row) for row in rows]
    })
