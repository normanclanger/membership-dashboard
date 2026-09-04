import hashlib

from database import get_connection
from responses import (
    success,
    bad_request,
    not_found,
    forbidden,
)


ALLOWED_ADMIN_GROUPS = {
    "PaymentAdmin",
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
        for group in groups.replace(",", " ").split()
        if group.strip()
    }


def can_administer(event):
    groups = get_user_groups(event)

    print("Gift Aid declaration admin groups:", groups)

    return bool(groups.intersection(ALLOWED_ADMIN_GROUPS))


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def lambda_handler(event, context):

    params = event.get("queryStringParameters") or {}

    token = params.get("token")
    member_id = params.get("member_id")

    # ------------------------------------------------------------
    # Access path validation
    # ------------------------------------------------------------

    if token and member_id:
        return bad_request({
            "error": "Specify either token or member_id, not both"
        })

    if not token and not member_id:
        return bad_request({
            "error": "Either token or member_id is required"
        })

    # ------------------------------------------------------------
    # Member ID access requires administration
    # ------------------------------------------------------------

    if member_id:

        if not can_administer(event):
            return forbidden({
                "error": "Gift Aid administration access required"
            })

        try:
            member_id = int(member_id)
        except (TypeError, ValueError):
            return bad_request({
                "error": "Invalid member_id"
            })

        if member_id <= 0:
            return bad_request({
                "error": "Invalid member_id"
            })

    # ------------------------------------------------------------
    # Database
    # ------------------------------------------------------------

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ----------------------------------------------------
            # Token path
            # ----------------------------------------------------

            if token:

                token_hash = hash_token(token)

                cur.execute("""
                    SELECT
                        id,
                        member_id,
                        gift_aid_reference,
                        expires_at,
                        used_at
                    FROM gift_aid_invitations
                    WHERE token_hash = %s;
                """, (token_hash,))

                invitation = cur.fetchone()

                if invitation is None:
                    return not_found({
                        "error": "Invalid invitation token"
                    })

                invitation_id = invitation[0]
                member_id = invitation[1]
                gift_aid_reference = invitation[2]
                expires_at = invitation[3]
                used_at = invitation[4]

                if used_at is not None:
                    return forbidden({
                        "error": "This invitation has already been used"
                    })

                if expires_at is not None:

                    cur.execute("""
                        SELECT NOW() > %s;
                    """, (expires_at,))

                    expired = cur.fetchone()[0]

                    if expired:
                        return forbidden({
                            "error": "This invitation has expired"
                        })

            # ----------------------------------------------------
            # Authenticated member ID path
            # ----------------------------------------------------

            else:

                cur.execute("""
                    SELECT
                        ga.gift_aid_reference
                    FROM gift_aid_members ga
                    WHERE ga.member_id = %s
                      AND (
                          ga.valid_until IS NULL
                          OR ga.valid_until >= CURRENT_DATE
                      )
                    ORDER BY ga.gift_aid_reference DESC
                    LIMIT 1;
                """, (member_id,))

                relationship = cur.fetchone()

                if relationship is None:
                    return not_found({
                        "error": "No active Gift Aid relationship found"
                    })

                gift_aid_reference = relationship[0]
                invitation_id = None

            # ----------------------------------------------------
            # Confirm the member itself exists
            # ----------------------------------------------------

            cur.execute("""
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
            """, (member_id,))

            member = cur.fetchone()

            if member is None:
                return not_found({
                    "error": "Member not found"
                })

            # ----------------------------------------------------
            # Get all currently active members on this
            # Gift Aid reference
            # ----------------------------------------------------

            cur.execute("""
                SELECT
                    ga.member_id,
                    m.membership_number,
                    m.first_name,
                    m.surname,
                    t.tower_name
                FROM gift_aid_members ga
                JOIN members m
                    ON ga.member_id = m.id
                LEFT JOIN towers t
                    ON m.tower_id = t.id
                WHERE ga.gift_aid_reference = %s
                  AND (
                      ga.valid_until IS NULL
                      OR ga.valid_until >= CURRENT_DATE
                  )
                ORDER BY
                    m.surname,
                    m.first_name;
            """, (gift_aid_reference,))

            member_rows = cur.fetchall()

            members = [
                {
                    "member_id": row[0],
                    "membership_number": row[1],
                    "first_name": row[2],
                    "surname": row[3],
                    "tower": row[4],
                }
                for row in member_rows
            ]

            # ----------------------------------------------------
            # Get most recent declaration audit record for this
            # Gift Aid reference
            # ----------------------------------------------------

            cur.execute("""
                SELECT
                    id,
                    action,
                    declaration_method,
                    declarer_name,
                    declarer_address,
                    email_address,
                    declaration_date,
                    recorded_at,
                    wording_version_id
                FROM gift_aid_declaration_audit
                WHERE gift_aid_reference = %s
                ORDER BY recorded_at DESC, id DESC
                LIMIT 1;
            """, (gift_aid_reference,))

            audit_row = cur.fetchone()

            declaration = None

            if audit_row is not None:

                declaration = {
                    "id": audit_row[0],
                    "action": audit_row[1],
                    "declaration_method": audit_row[2],
                    "declarer_name": audit_row[3],
                    "declarer_address": audit_row[4],
                    "email_address": audit_row[5],
                    "declaration_date": (
                        audit_row[6].isoformat()
                        if audit_row[6]
                        else None
                    ),
                    "recorded_at": (
                        audit_row[7].isoformat()
                        if audit_row[7]
                        else None
                    ),
                    "wording_version_id": audit_row[8],
                }

            # ----------------------------------------------------
            # Return declaration
            # ----------------------------------------------------

            return success({
                "gift_aid_reference": gift_aid_reference,
                "member_id": member_id,
                "invitation_id": invitation_id,
                "member": {
                    "member_id": member[0],
                    "membership_number": member[1],
                    "first_name": member[2],
                    "surname": member[3],
                    "tower": member[4],
                },
                "members": members,
                "declaration": declaration,
            })

    finally:
        conn.close()