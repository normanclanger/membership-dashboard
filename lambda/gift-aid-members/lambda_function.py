from database import get_connection
from responses import success, bad_request, not_found, conflict, forbidden


ALLOWED_WRITE_GROUPS = {
    "PaymentAdmin",
    "ApplicationAdmin",
    "MembershipAdmin",
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


def can_write(event):
    groups = get_user_groups(event)
    
    print("Gift Aid user groups:", groups)

    return bool(
        groups.intersection(ALLOWED_WRITE_GROUPS)
    )


def lambda_handler(event, context):

    route = event.get("routeKey")

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # =====================================================
            # GET /api/gift-aid
            #
            # Query by member_id OR gift_aid_reference
            # If neither is supplied, return all relationships.
            # =====================================================

            if route == "GET /api/gift-aid":

                params = event.get("queryStringParameters") or {}

                member_id = params.get("member_id")
                gift_aid_reference = params.get(
                    "gift_aid_reference"
                )

                if member_id and gift_aid_reference:
                    return bad_request({
                        "error": (
                            "Specify either member_id or "
                            "gift_aid_reference, not both"
                        )
                    })

                if member_id:

                    try:
                        member_id = int(member_id)
                    except ValueError:
                        return bad_request({
                            "error": "Invalid member_id"
                        })

                    cur.execute(
                        """
                        SELECT
                            ga.id,
                            ga.member_id,
                            m.membership_number,
                            m.first_name,
                            m.surname,
                            t.tower_name,
                            ga.gift_aid_reference
                        FROM gift_aid_members ga
                        JOIN members m
                            ON ga.member_id = m.id
                        LEFT JOIN towers t
                            ON m.tower_id = t.id
                        WHERE ga.member_id = %s
                        ORDER BY ga.gift_aid_reference DESC;
                        """,
                        (member_id,)
                    )

                elif gift_aid_reference:

                    try:
                        gift_aid_reference = int(
                            gift_aid_reference
                        )
                    except ValueError:
                        return bad_request({
                            "error": "Invalid gift_aid_reference"
                        })

                    cur.execute(
                        """
                        SELECT
                            ga.id,
                            ga.member_id,
                            m.membership_number,
                            m.first_name,
                            m.surname,
                            t.tower_name,
                            ga.gift_aid_reference
                        FROM gift_aid_members ga
                        JOIN members m
                            ON ga.member_id = m.id
                        LEFT JOIN towers t
                            ON m.tower_id = t.id
                        WHERE ga.gift_aid_reference = %s
                        ORDER BY m.surname, m.first_name;
                        """,
                        (gift_aid_reference,)
                    )

                else:

                    cur.execute(
                        """
                        SELECT
                            ga.id,
                            ga.member_id,
                            m.membership_number,
                            m.first_name,
                            m.surname,
                            t.tower_name,
                            ga.gift_aid_reference
                        FROM gift_aid_members ga
                        JOIN members m
                            ON ga.member_id = m.id
                        LEFT JOIN towers t
                            ON m.tower_id = t.id
                        ORDER BY
                            ga.gift_aid_reference,
                            m.surname,
                            m.first_name;
                        """
                    )

                rows = cur.fetchall()

                return success({
                    "relationships": [
                        {
                            "id": row[0],
                            "member_id": row[1],
                            "membership_number": row[2],
                            "first_name": row[3],
                            "surname": row[4],
                            "tower": row[5],
                            "gift_aid_reference": row[6]
                        }
                        for row in rows
                    ]
                })

            # =====================================================
            # POST /api/gift-aid
            # =====================================================

            if route == "POST /api/gift-aid":

                if not can_write(event):
                    return forbidden({
                        "error": "Write access required"
                    })

                body = event.get("body")

                if not body:
                    return bad_request({
                        "error": "Request body is required"
                    })

                import json

                try:
                    data = json.loads(body)
                except (TypeError, json.JSONDecodeError):
                    return bad_request({
                        "error": "Invalid JSON"
                    })

                member_id = data.get("member_id")
                gift_aid_reference = data.get(
                    "gift_aid_reference"
                )

                if member_id is None:
                    return bad_request({
                        "error": "member_id is required"
                    })

                if gift_aid_reference is None:
                    return bad_request({
                        "error": "gift_aid_reference is required"
                    })

                try:
                    member_id = int(member_id)
                    gift_aid_reference = int(
                        gift_aid_reference
                    )
                except (TypeError, ValueError):
                    return bad_request({
                        "error": (
                            "member_id and gift_aid_reference "
                            "must be numbers"
                        )
                    })

                if member_id <= 0:
                    return bad_request({
                        "error": "Invalid member_id"
                    })

                if gift_aid_reference <= 0:
                    return bad_request({
                        "error": "Invalid gift_aid_reference"
                    })

                # Confirm that the member exists and obtain
                # the information needed by the UI.

                cur.execute(
                    """
                    SELECT
                        m.id,
                        m.membership_number,
                        m.first_name,
                        m.surname,
                        t.tower_name
                    FROM members m
                    LEFT JOIN towers t
                        ON m.tower_id = t.id
                    WHERE m.id = %s;
                    """,
                    (member_id,)
                )

                member = cur.fetchone()

                if member is None:
                    return not_found({
                        "error": "Member not found"
                    })

                # Prevent duplicate relationships.

                cur.execute(
                    """
                    SELECT id
                    FROM gift_aid_members
                    WHERE member_id = %s
                      AND gift_aid_reference = %s;
                    """,
                    (
                        member_id,
                        gift_aid_reference
                    )
                )

                existing = cur.fetchone()

                if existing is not None:
                    return conflict({
                        "error": (
                            "This Gift Aid relationship "
                            "already exists"
                        ),
                        "id": existing[0]
                    })

                cur.execute(
                    """
                    INSERT INTO gift_aid_members (
                        member_id,
                        gift_aid_reference
                    )
                    VALUES (%s, %s)
                    RETURNING id;
                    """,
                    (
                        member_id,
                        gift_aid_reference
                    )
                )

                relationship_id = cur.fetchone()[0]

                conn.commit()

                return success({
                    "id": relationship_id,
                    "member_id": member[0],
                    "membership_number": member[1],
                    "first_name": member[2],
                    "surname": member[3],
                    "tower": member[4],
                    "gift_aid_reference": gift_aid_reference
                })

            # =====================================================
            # DELETE /api/gift-aid/{id}
            # =====================================================

            if route == "DELETE /api/gift-aid/{id}":

                if not can_write(event):
                    return forbidden({
                        "error": "Write access required"
                    })

                path_parameters = (
                    event.get("pathParameters") or {}
                )

                relationship_id = path_parameters.get("id")

                if not relationship_id:
                    return bad_request({
                        "error": "Gift Aid relationship id is required"
                    })

                try:
                    relationship_id = int(
                        relationship_id
                    )
                except ValueError:
                    return bad_request({
                        "error": "Invalid Gift Aid relationship id"
                    })

                cur.execute(
                    """
                    SELECT
                        ga.id,
                        ga.member_id,
                        m.membership_number,
                        m.first_name,
                        m.surname,
                        t.tower_name,
                        ga.gift_aid_reference
                    FROM gift_aid_members ga
                    JOIN members m
                        ON ga.member_id = m.id
                    LEFT JOIN towers t
                        ON m.tower_id = t.id
                    WHERE ga.id = %s;
                    """,
                    (relationship_id,)
                )

                relationship = cur.fetchone()

                if relationship is None:
                    return not_found({
                        "error": "Gift Aid relationship not found"
                    })

                cur.execute(
                    """
                    DELETE FROM gift_aid_members
                    WHERE id = %s;
                    """,
                    (relationship_id,)
                )

                conn.commit()

                return success({
                    "deleted": True,
                    "id": relationship[0],
                    "member_id": relationship[1],
                    "membership_number": relationship[2],
                    "first_name": relationship[3],
                    "surname": relationship[4],
                    "tower": relationship[5],
                    "gift_aid_reference": relationship[6]
                })

            return bad_request({
                "error": "Unknown route"
            })

    finally:
        conn.close()