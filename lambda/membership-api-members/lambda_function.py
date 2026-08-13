import json

from database import get_connection
from responses import (
    success,
    created,
    bad_request,
    not_found,
    conflict,
    forbidden
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

def member_detail_from_row(row):
    return {
        "id": row[0],
        "membership_number": row[1],
        "first_name": row[2],
        "surname": row[3],
        "tower": {
            "id": row[4],
            "name": row[5]
        } if row[4] is not None else None,
        "district": {
            "id": row[6],
            "code": row[7],
            "name": row[8]
        } if row[6] is not None else None,
        "date_of_birth": row[9].isoformat() if row[9] else None,
        "membership_class": {
            "id": row[10],
            "code": row[11],
            "name": row[12]
        } if row[10] is not None else None,
        "membership_status": {
            "id": row[13],
            "code": row[14],
            "name": row[15]
        } if row[13] is not None else None,
        "full_member_type": {
            "id": row[16],
            "code": row[17],
            "name": row[18]
        } if row[16] is not None else None
    }


# logic to determine if the user has permission to edit members

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


def can_edit_members(event):
    groups = get_user_groups(event)

    return bool(
        groups.intersection({
            "MembershipAdmin",
            "ApplicationAdmin"
        })
    )


def lambda_handler(event, context):
    http_method = event.get("requestContext", {}).get("http", {}).get("method")

    # ---------------------------------------------------------
    # POST /api/members
    # ---------------------------------------------------------
    if http_method == "POST":

        if not can_edit_members(event):
            return forbidden({
            "error": "You do not have permission to create members"
        })

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
    # PATCH /api/members/{id}
    # ---------------------------------------------------------
    if http_method == "PATCH":


        path_parameters = event.get("pathParameters") or {}
        member_id = path_parameters.get("id")

        if not can_edit_members(event):
            return forbidden({
                "error": "You do not have permission to edit members"
            })

        if not member_id:
            return bad_request({
                "error": "Member ID is required"
            })

        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return bad_request({
                "error": "Request body must contain valid JSON"
            })

        allowed_fields = {
            "first_name",
            "surname",
            "tower_id",
            "date_of_birth",
            "membership_class_id",
            "membership_status_id",
            "full_member_type_id"
        }

        unknown_fields = set(body) - allowed_fields

        if unknown_fields:
            return bad_request({
                "error": "Unknown fields",
                "fields": sorted(unknown_fields)
            })

        if not body:
            return bad_request({
                "error": "No fields supplied for update"
            })

        conn = get_connection()

        try:
            with conn.cursor() as cur:

                # First confirm the member exists.
                cur.execute(
                    "SELECT id FROM members WHERE id = %s;",
                    (member_id,)
                )

                if cur.fetchone() is None:
                    return not_found({
                        "error": "Member not found"
                    })

                set_clauses = []
                values = []

                column_map = {
                    "first_name": "first_name",
                    "surname": "surname",
                    "tower_id": "tower_id",
                    "date_of_birth": "date_of_birth",
                    "membership_class_id": "membership_class_id",
                    "membership_status_id": "membership_status_id",
                    "full_member_type_id": "full_member_type_id"
                }

                for field in body:
                    set_clauses.append(f"{column_map[field]} = %s")
                    values.append(body[field])

                values.append(member_id)

                try:
                    cur.execute(
                        f"""
                        UPDATE members
                        SET {", ".join(set_clauses)}
                        WHERE id = %s
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
                        values
                    )

                    row = cur.fetchone()
                    conn.commit()

                except Exception as exc:
                    conn.rollback()

                    if getattr(exc, "sqlstate", None) == "23505":
                        return conflict({
                            "error": "Membership number already exists"
                        })

                    if getattr(exc, "sqlstate", None) == "23503":
                        return bad_request({
                            "error": "One or more referenced records do not exist"
                        })

                    raise

        finally:
            conn.close()

        return success({
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
                        m.id,
                        m.membership_number,
                        m.first_name,
                        m.surname,

                        t.id,
                        t.tower_name,

                        d.id,
                        d.code,
                        d.name,

                        m.date_of_birth,

                        mc.id,
                        mc.code,
                        mc.name,

                        ms.id,
                        ms.code,
                        ms.name,

                        fmt.id,
                        fmt.code,
                        fmt.name

                    FROM members m

                    JOIN towers t
                        ON m.tower_id = t.id

                    JOIN districts d
                        ON t.district_id = d.id

                    LEFT JOIN membership_classes mc
                        ON m.membership_class_id = mc.id

                    LEFT JOIN membership_statuses ms
                        ON m.membership_status_id = ms.id

                    LEFT JOIN full_member_types fmt
                        ON m.full_member_type_id = fmt.id

                    WHERE m.id = %s;
                    """,
                    (member_id,)
                )

                row = cur.fetchone()

                if row is None:
                    return not_found({
                        "error": "Member not found"
                    })

                return success({
                    "member": member_detail_from_row(row)
                })

            if search:
                cur.execute(
                    """
                    SELECT
                        m.id,
                        m.membership_number,
                        m.first_name,
                        m.surname,

                        t.id,
                        t.tower_name,

                        d.id,
                        d.code,
                        d.name,

                        m.date_of_birth,

                        mc.id,
                        mc.code,
                        mc.name,

                        ms.id,
                        ms.code,
                        ms.name,

                        fmt.id,
                        fmt.code,
                        fmt.name

                    FROM members m

                    JOIN towers t
                        ON m.tower_id = t.id

                    JOIN districts d
                        ON t.district_id = d.id

                    LEFT JOIN membership_classes mc
                        ON m.membership_class_id = mc.id

                    LEFT JOIN membership_statuses ms
                        ON m.membership_status_id = ms.id

                    LEFT JOIN full_member_types fmt
                        ON m.full_member_type_id = fmt.id

                    WHERE m.membership_number ILIKE %s
                       OR m.first_name ILIKE %s
                       OR m.surname ILIKE %s

                    ORDER BY m.surname, m.first_name;
                    """,
                    (
                        f"%{search}%",
                        f"%{search}%",
                        f"%{search}%"
                    )
                )


            else:
                cur.execute(
                    """
                    SELECT
                        m.id,
                        m.membership_number,
                        m.first_name,
                        m.surname,

                        t.id,
                        t.tower_name,

                        d.id,
                        d.code,
                        d.name,

                        m.date_of_birth,

                        mc.id,
                        mc.code,
                        mc.name,

                        ms.id,
                        ms.code,
                        ms.name,

                        fmt.id,
                        fmt.code,
                        fmt.name

                    FROM members m

                    JOIN towers t
                        ON m.tower_id = t.id

                    JOIN districts d
                        ON t.district_id = d.id

                    LEFT JOIN membership_classes mc
                        ON m.membership_class_id = mc.id

                    LEFT JOIN membership_statuses ms
                        ON m.membership_status_id = ms.id

                    LEFT JOIN full_member_types fmt
                        ON m.full_member_type_id = fmt.id

                    ORDER BY m.surname, m.first_name;
                    """
               )
            
            rows = cur.fetchall()

            cur.execute(
                """
                SELECT membership_number
                FROM members
                ORDER BY id DESC
                LIMIT 1;
                """
            )

            last_created_row = cur.fetchone()
            
            return success({
                "members": [member_detail_from_row(row) for row in rows],
                "last_created": {
                "membership_number": last_created_row[0]
            } if last_created_row else None
            })

    finally:
        conn.close()



