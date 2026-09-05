import hashlib
import json

from database import get_connection
from responses import (
    success,
    bad_request,
    not_found,
    forbidden,
    created,
)


ALLOWED_ADMIN_GROUPS = {
    "paymentAdmin",
    "membershipAdmin",
}


VALID_ACTIONS = {
    "AFFIRMED",
    "CANCELLED",
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

    return {
        group.strip().strip("'\"")
        for group in groups.replace(",", " ").split()
        if group.strip()
    }


def can_administer(event):

    groups = get_user_groups(event)

    return bool(
        groups.intersection(ALLOWED_ADMIN_GROUPS)
    )


def hash_token(token):

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def lambda_handler(event, context):

    params = (
        event.get("queryStringParameters")
        or {}
    )

    token = params.get("token")
    member_id = params.get("member_id")

    # ------------------------------------------------------------
    # Validate access method
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
    # Parse request body
    # ------------------------------------------------------------

    try:

        body = json.loads(
            event.get("body") or "{}"
        )

    except json.JSONDecodeError:

        return bad_request({
            "error": "Invalid JSON body"
        })

    action = body.get("action")

    if action not in VALID_ACTIONS:

        return bad_request({
            "error": "Invalid action"
        })

    # ------------------------------------------------------------
    # Authenticated admin path
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

            invitation_id = None

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
                    WHERE token_hash = %s
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

                    cur.execute(
                        "SELECT NOW() > %s",
                        (expires_at,)
                    )

                    if cur.fetchone()[0]:

                        return forbidden({
                            "error": "This invitation has expired"
                        })

            # ----------------------------------------------------
            # Admin member_id path
            # ----------------------------------------------------

            else:

                cur.execute("""
                    SELECT
                        gift_aid_reference
                    FROM gift_aid_members
                    WHERE member_id = %s
                      AND (
                          valid_until IS NULL
                          OR valid_until >= CURRENT_DATE
                      )
                    ORDER BY gift_aid_reference DESC
                    LIMIT 1
                """, (member_id,))

                relationship = cur.fetchone()

                if relationship is None:

                    return not_found({
                        "error": "No active Gift Aid relationship found"
                    })

                gift_aid_reference = relationship[0]

            # ----------------------------------------------------
            # Current declaration
            # ----------------------------------------------------

            cur.execute("""
                SELECT
                    declarer_name,
                    declarer_address,
                    email_address
                FROM gift_aid_declaration_audit
                WHERE gift_aid_reference = %s
                ORDER BY recorded_at DESC, id DESC
                LIMIT 1
            """, (gift_aid_reference,))

            current = cur.fetchone()

            if current is None:

                return not_found({
                    "error": "Gift Aid declaration not found"
                })

            current_name = current[0]
            current_address = current[1]
            current_email = current[2]

            # ----------------------------------------------------
            # Use submitted values where supplied
            # ----------------------------------------------------

            declarer_name = (
                body.get("declarer_name")
                or current_name
            )

            declarer_address = (
                body.get("declarer_address")
                or current_address
            )

            email_address = (
                body.get("email_address")
                or current_email
            )

            declaration_date = (
                body.get("declaration_date")
            )

            wording_version_id = (
                body.get("wording_version_id")
            )

            declaration_text = (
                body.get("declaration_text")
            )

            # ----------------------------------------------------
            # Validate declaration data
            # ----------------------------------------------------

            if not declarer_name:

                return bad_request({
                    "error": "declarer_name is required"
                })

            if not declarer_address:

                return bad_request({
                    "error": "declarer_address is required"
                })

            if not declaration_date:

                return bad_request({
                    "error": "declaration_date is required"
                })

            if not wording_version_id:

                return bad_request({
                    "error": "wording_version_id is required"
                })

            if not declaration_text:

                return bad_request({
                    "error": "declaration_text is required"
                })

            # ----------------------------------------------------
            # Members submitted by the form
            # ----------------------------------------------------

            submitted_members = body.get(
                "members"
            )

            if submitted_members is None:

                submitted_members = [
                    member_id
                ]

            if not isinstance(
                submitted_members,
                list
            ):

                return bad_request({
                    "error": "members must be a list"
                })

            try:

                submitted_members = {
                    int(value)
                    for value in submitted_members
                }

            except (TypeError, ValueError):

                return bad_request({
                    "error": "Invalid member ID in members"
                })

            # ----------------------------------------------------
            # Get current members on declaration
            # ----------------------------------------------------

            cur.execute("""
                SELECT
                    member_id
                FROM gift_aid_members
                WHERE gift_aid_reference = %s
                  AND (
                      valid_until IS NULL
                      OR valid_until >= %s
                  )
            """, (
                gift_aid_reference,
                declaration_date,
            ))

            existing_members = {
                row[0]
                for row in cur.fetchall()
            }

            # ----------------------------------------------------
            # A token user may only remove members.
            #
            # They cannot add arbitrary member IDs.
            # ----------------------------------------------------

            if token:

                if not submitted_members.issubset(
                    existing_members
                ):

                    return bad_request({
                        "error":
                        "Online declaration cannot add members"
                    })

            # ----------------------------------------------------
            # Members being removed
            # ----------------------------------------------------

            removed_members = (
                existing_members -
                submitted_members
            )

            # ----------------------------------------------------
            # Cancellation means all relationships end
            # ----------------------------------------------------

            if action == "CANCELLED":

                removed_members = existing_members

            # ----------------------------------------------------
            # End removed relationships
            # ----------------------------------------------------

            for removed_member_id in removed_members:

                cur.execute("""
                    UPDATE gift_aid_members
                    SET valid_until = %s
                    WHERE gift_aid_reference = %s
                      AND member_id = %s
                      AND (
                          valid_until IS NULL
                          OR valid_until >= %s
                      )
                """, (
                    declaration_date,
                    gift_aid_reference,
                    removed_member_id,
                    declaration_date,
                ))

            # ----------------------------------------------------
            # Create audit record
            # ----------------------------------------------------

            cur.execute("""
                INSERT INTO gift_aid_declaration_audit (
                    member_id,
                    gift_aid_reference,
                    action,
                    declaration_method,
                    declaration_text,
                    declarer_name,
                    declarer_address,
                    email_address,
                    declaration_date,
                    ip_address,
                    user_agent,
                    invitation_id,
                    wording_version_id
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'ONLINE',
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
            """, (
                member_id,
                gift_aid_reference,
                action,
                declaration_text,
                declarer_name,
                declarer_address,
                email_address,
                declaration_date,
                (
                    event.get("requestContext", {})
                    .get("http", {})
                    .get("sourceIp")
                ),
                event.get("headers", {})
                    .get("user-agent"),
                invitation_id,
                wording_version_id,
            ))

            audit_id = cur.fetchone()[0]

            # ----------------------------------------------------
            # Mark invitation used
            # ----------------------------------------------------

            if invitation_id:

                cur.execute("""
                    UPDATE gift_aid_invitations
                    SET used_at = NOW()
                    WHERE id = %s
                """, (invitation_id,))

            conn.commit()

            return created({
                "gift_aid_reference":
                    gift_aid_reference,
                "member_id":
                    member_id,
                "invitation_id":
                    invitation_id,
                "audit_id":
                    audit_id,
                "action":
                    action,
                "members":
                    sorted(submitted_members),
                "removed_members":
                    sorted(removed_members),
            })

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()