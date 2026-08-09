from database import get_connection
from responses import success


def lambda_handler(event, context):
    path_parameters = event.get("pathParameters") or {}
    member_id = path_parameters.get("id")

    query_parameters = event.get("queryStringParameters") or {}
    search = query_parameters.get("search")

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # Get one member
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
                    return {
                        "statusCode": 404,
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "body": '{"error": "Member not found"}'
                    }

                member = {
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

                return success({
                    "member": member
                })

            # List/search members
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

    members = [
        {
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
        for row in rows
    ]

    return success({
        "members": members
    })
