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
    "PaymentAdmin",
    "MembershipAdmin",
}


VALID_ACTIONS = {
    "AFFIRMED",
    "UPDATED",
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

    if not groups:
        return set()

    return {
        group.strip().strip("'\"")
        for group in groups.replace(",", " ").split()
        if group.strip()
    }


def get_cognito_sub(event):

    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    return claims.get("sub")


def can_administer(event):

    groups = get_user_groups(event)

    print("Gift Aid declaration admin groups:", groups)

    return bool(
        groups.intersection(ALLOWED_ADMIN_GROUPS)
    )


def hash_token(token):

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def get_source_ip(event):

    return (
        event.get("requestContext", {})
        .get("http", {})
        .get("sourceIp")
    )


def get_user_agent(event):

    headers = event.get("headers") or {}

    return (
        headers.get("user-agent")
        or headers.get("User-Agent")
    )


def lambda_handler(event, context):

    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
    )

    if method == "GET":
        return handle_get(event)

    if method == "POST":
        return handle_post(event)

    return bad_request({
        "error": "Method not supported"
    })


# =================================================================
# GET
# =================================================================

def handle_get(event):

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
            #
            # A new online invitation may have NULL reference.
            # In that case this simply returns no relationships.
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
            # Get most recent declaration audit record
            # ----------------------------------------------------

            declaration = None

            if gift_aid_reference is not None:

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


# =================================================================
# POST
# =================================================================

def handle_post(event):

    params = event.get("queryStringParameters") or {}

    token = params.get("token")
    member_id_param = params.get("member_id")

    # ------------------------------------------------------------
    # Access path validation
    # ------------------------------------------------------------

    if token and member_id_param:
        return bad_request({
            "error": "Specify either token or member_id, not both"
        })

    if not token and not member_id_param:
        return bad_request({
            "error": "Either token or member_id is required"
        })

    # ------------------------------------------------------------
    # Parse body
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
    # Determine access method
    # ------------------------------------------------------------

    is_token_request = bool(token)

    if member_id_param:

        if not can_administer(event):
            return forbidden({
                "error": "Gift Aid administration access required"
            })

        try:
            member_id = int(member_id_param)
        except (TypeError, ValueError):
            return bad_request({
                "error": "Invalid member_id"
            })

        if member_id <= 0:
            return bad_request({
                "error": "Invalid member_id"
            })

        declaration_method = "MANUAL"

        cognito_sub = get_cognito_sub(event)

        if not cognito_sub:
            return forbidden({
                "error": "Authenticated user identity not available"
            })

        recorded_by = cognito_sub

    else:

        member_id = None
        declaration_method = "ONLINE"
        recorded_by = None

    # ------------------------------------------------------------
    # Declaration data
    # ------------------------------------------------------------

    declarer_name = body.get("declarer_name")
    declarer_address = body.get("declarer_address")
    email_address = body.get("email_address")
    declaration_date = body.get("declaration_date")
    wording_version_id = body.get("wording_version_id")
    declaration_text = body.get("declaration_text")

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

    # ------------------------------------------------------------
    # Members submitted by the form
    # ------------------------------------------------------------

    submitted_members = body.get("members")

    if submitted_members is None:
        return bad_request({
            "error": "members is required"
        })

    if not isinstance(submitted_members, list):
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

    if any(value <= 0 for value in submitted_members):

        return bad_request({
            "error": "Invalid member ID in members"
        })

    # A cancellation does not need submitted members.
    if action != "CANCELLED" and not submitted_members:

        return bad_request({
            "error": "At least one member is required"
        })

    # ------------------------------------------------------------
    # Database
    # ------------------------------------------------------------

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            invitation_id = None
            gift_aid_reference = None
            existing_members = set()
            declaration_exists = False
            reference_supplied = False

            # ====================================================
            # TOKEN
            # ====================================================

            if is_token_request:

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

                # If the invitation already has a reference,
                # this is an UPDATE/CANCEL.
                #
                # If it has no reference, this is a CREATE.

            # ====================================================
            # ADMIN
            # ====================================================

            else:

                requested_reference = body.get(
                    "gift_aid_reference"
                )

                if requested_reference is not None:

                    try:

                        requested_reference = int(
                            requested_reference
                        )

                    except (TypeError, ValueError):

                        return bad_request({
                            "error": "Invalid gift_aid_reference"
                        })

                    if requested_reference <= 0:

                        return bad_request({
                            "error": "Invalid gift_aid_reference"
                        })

                    gift_aid_reference = requested_reference
                    reference_supplied = True

                else:

                    # If no reference was supplied, find the
                    # member's current active Gift Aid relationship.
                    cur.execute("""
                        SELECT
                            gift_aid_reference
                        FROM gift_aid_members
                        WHERE member_id = %s
                          AND (
                              valid_until IS NULL
                              OR valid_until >= %s
                          )
                        ORDER BY gift_aid_reference DESC
                        LIMIT 1
                    """, (
                        member_id,
                        declaration_date,
                    ))

                    relationship = cur.fetchone()

                    if relationship is not None:

                        gift_aid_reference = relationship[0]

            # ====================================================
            # DETERMINE WHETHER REFERENCE ALREADY HAS A DECLARATION
            # ====================================================

            if gift_aid_reference is not None:

                cur.execute("""
                    SELECT 1
                    FROM gift_aid_declaration_audit
                    WHERE gift_aid_reference = %s
                    LIMIT 1
                """, (gift_aid_reference,))

                declaration_exists = (
                    cur.fetchone() is not None
                )

            # ====================================================
            # ONLINE CREATE
            # ====================================================

            if (
                is_token_request
                and gift_aid_reference is None
            ):

                # New online declaration gets a system-generated
                # reference from the 900000+ sequence.
                cur.execute("""
                    SELECT nextval(
                        'gift_aid_reference_seq'
                    )
                """)

                gift_aid_reference = cur.fetchone()[0]

                declaration_exists = False

            # ====================================================
            # ADMIN CREATE
            # ====================================================

            if (
                not is_token_request
                and not declaration_exists
            ):

                # A new manual declaration MUST have the reference
                # from the paper form.
                if not reference_supplied:

                    return bad_request({
                        "error":
                        "gift_aid_reference is required for a new paper declaration"
                    })

                # New declarations must be affirmed.
                if action != "AFFIRMED":

                    return bad_request({
                        "error":
                        "A new declaration must use action AFFIRMED"
                    })

            # ====================================================
            # CONFIRM DECLARER MEMBER EXISTS
            # ====================================================

            cur.execute("""
                SELECT 1
                FROM members
                WHERE id = %s
            """, (member_id,))

            if cur.fetchone() is None:

                return not_found({
                    "error": "Member not found"
                })

            # ====================================================
            # GET CURRENT ACTIVE MEMBERS
            # ====================================================

            if declaration_exists:

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

            # ====================================================
            # VALIDATE SUBMITTED MEMBER IDS
            #
            # The declarer may nominate ANY existing Guild member.
            # ====================================================

            if submitted_members:

                cur.execute("""
                    SELECT id
                    FROM members
                    WHERE id = ANY(%s)
                """, (
                    list(submitted_members),
                ))

                valid_member_ids = {
                    row[0]
                    for row in cur.fetchall()
                }

                invalid_members = (
                    submitted_members
                    - valid_member_ids
                )

                if invalid_members:

                    return bad_request({
                        "error":
                        "One or more members do not exist",
                        "invalid_members":
                        sorted(invalid_members),
                    })

            # ====================================================
            # DETERMINE ADDED / REMOVED MEMBERS
            # ====================================================

            if action == "CANCELLED":

                added_members = set()
                removed_members = existing_members

            else:

                added_members = (
                    submitted_members
                    - existing_members
                )

                removed_members = (
                    existing_members
                    - submitted_members
                )

            # ====================================================
            # ADD MEMBERS
            # ====================================================

            for new_member_id in added_members:

                cur.execute("""
                    INSERT INTO gift_aid_members (
                        member_id,
                        gift_aid_reference,
                        valid_until
                    )
                    VALUES (
                        %s,
                        %s,
                        NULL
                    )
                """, (
                    new_member_id,
                    gift_aid_reference,
                ))

            # ====================================================
            # END REMOVED MEMBERS
            # ====================================================

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

            # ====================================================
            # DETERMINE AUDIT ACTION
            # ====================================================

            if not declaration_exists:

                audit_action = "AFFIRMED"

            elif action == "CANCELLED":

                audit_action = "CANCELLED"

            else:

                audit_action = "UPDATED"

            # ====================================================
            # RECORD WHO SUBMITTED IT
            # ====================================================

            if is_token_request:

                # For an unauthenticated invitation submission,
                # recorded_by is the declarer's member ID.
                recorded_by = str(member_id)

            # For admin, recorded_by was already set to Cognito sub.

            # ====================================================
            # AUDIT RECORD
            # ====================================================

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
                    recorded_by,
                    wording_version_id
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
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
                audit_action,
                declaration_method,
                declaration_text,
                declarer_name,
                declarer_address,
                email_address,
                declaration_date,
                get_source_ip(event),
                get_user_agent(event),
                invitation_id,
                recorded_by,
                wording_version_id,
            ))

            audit_id = cur.fetchone()[0]

            # ====================================================
            # COMPLETE ONLINE INVITATION
            # ====================================================

            if invitation_id:

                cur.execute("""
                    UPDATE gift_aid_invitations
                    SET
                        gift_aid_reference = %s,
                        used_at = NOW()
                    WHERE id = %s
                """, (
                    gift_aid_reference,
                    invitation_id,
                ))

            # ====================================================
            # COMMIT
            # ====================================================

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
                    audit_action,
                "declaration_method":
                    declaration_method,
                "members":
                    sorted(
                        submitted_members
                        if action != "CANCELLED"
                        else existing_members
                    ),
                "added_members":
                    sorted(added_members),
                "removed_members":
                    sorted(removed_members),
            })

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()