from database import get_connection
from responses import success, bad_request, not_found


def lambda_handler(event, context):

    route = event.get("routeKey")

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            if route == "GET /api/towers":

                cur.execute(
                    """
                    SELECT
                        t.id,
                        t.tower_name,
                        d.code
                    FROM towers t
                    JOIN districts d
                        ON t.district_id = d.id
                    ORDER BY t.tower_name;
                    """
                )

                rows = cur.fetchall()

                return success({
                    "towers": [
                        {
                            "id": row[0],
                            "tower_name": row[1],
                            "district_code": row[2]
                        }
                        for row in rows
                    ]
                })

            if route == "GET /api/membership-classes":

                cur.execute(
                    """
                    SELECT
                        id,
                        code,
                        name
                    FROM membership_classes
                    ORDER BY name;
                    """
                )

                rows = cur.fetchall()

                return success({
                    "membership_classes": [
                        {
                            "id": row[0],
                            "code": row[1],
                            "name": row[2]
                        }
                        for row in rows
                    ]
                })

            if route == "GET /api/membership-statuses":

                cur.execute(
                    """
                    SELECT
                        id,
                        code,
                        name
                    FROM membership_statuses
                    ORDER BY name;
                    """
                )

                rows = cur.fetchall()

                return success({
                    "membership_statuses": [
                        {
                            "id": row[0],
                            "code": row[1],
                            "name": row[2]
                        }
                        for row in rows
                    ]
                })

            if route == "GET /api/full-member-types":

                cur.execute(
                    """
                    SELECT
                        id,
                        code,
                        name
                    FROM full_member_types
                    ORDER BY name;
                    """
                )

                rows = cur.fetchall()

                return success({
                    "full_member_types": [
                        {
                            "id": row[0],
                            "code": row[1],
                            "name": row[2]
                        }
                        for row in rows
                    ]
                })

            return bad_request({
                "error": "Unknown route"
            })

    finally:
        conn.close()
