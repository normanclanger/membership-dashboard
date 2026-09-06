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
    "DECLINED",
    "COVERED_ELSEWHERE",
}


PUBLIC_DECLARATION_PATH = "/api/gift-aid/declaration"
ADMIN_DECLARATION_PATH = "/api/gift-aid/admin/declaration"


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


def get_request_path(event):

    request_context = event.get("requestContext", {})

    http = request_context.get("http", {})

    return (
        event.get("rawPath")
        or http.get("path")
    )


def lambda_handler(event, context):

    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
    )

    path = get_request_path(event)

    print("Gift Aid declaration request:", method, path)

    # ------------------------------------------------------------
    # Confirm expected API route
    # ------------------------------------------------------------

    if path not in {
        PUBLIC_DECLARATION_PATH,
        ADMIN_DECLARATION_PATH,
    }:
        return bad_request({
            "error": "Invalid Gift Aid declaration route"
        })

    # ------------------------------------------------------------
    # Public token route
    # ------------------------------------------------------------

    if path == PUBLIC_DECLARATION_PATH:

        if method not in {"GET", "POST"}:
            return bad_request({
                "error": "Method not supported"
            })

        params = event.get("queryStringParameters") or {}

        token = params.get("token")
        member_id = params.get("member_id")

        if not token:
            return forbidden({
                "error":
                "Invitation token required for this route"
            })

        if member_id:
            return forbidden({
                "error":
                "member_id is not permitted on the public declaration route"
            })

    # ------------------------------------------------------------
    # Admin route
    # ------------------------------------------------------------

    elif path == ADMIN_DECLARATION_PATH:

        if method not in {"GET", "POST"}:
            return bad_request({
                "error": "Method not supported"
            })

        params = event.get("queryStringParameters") or {}

        token = params.get("token")
        member_id = params.get("member_id")

        if token:
            return forbidden({
                "error":
                "Invitation token is not permitted on the admin declaration route"
            })

        if not member_id:
            return bad_request({
                "error":
                "member_id is required for the admin declaration route"
            })

        if not can_administer(event):
            return forbidden({
                "error": "Gift Aid administration access required"
            })

    # ------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------

    if method == "GET":
        return handle_get(event, path)

    if method == "POST":
        return handle_post(event, path)

    return bad_request({
        "error": "Method not supported"
    })


# =================================================================
# GET
# =================================================================

def handle_get(event, path):

    params = event.get("queryStringParameters") or {}

    # ------------------------------------------------------------
    # Public token path
    # ------------------------------------------------------------

    if path == PUBLIC_DECLARATION_PATH:

        token = params.get("token")

        if not token:
            return bad_request({
                "error": "token is required"
            })

        member_id = None

    # ------------------------------------------------------------
    # Authenticated admin path
    # ------------------------------------------------------------

    elif path == ADMIN_DECLARATION_PATH:

        member_id_param = params.get("member_id")

        if not member_id_param:
            return bad_request({
                "error": "member_id is required"
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

        token = None

    else:

        return bad_request({
            "error": "Invalid Gift Aid declaration route"
        })

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            invitation_id = None
            gift_aid_reference = None

            # ====================================================
            # TOKEN PATH
            # ====================================================

            if path == PUBLIC_DECLARATION_PATH:

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
                        "error":
                        "This invitation has already been used"
                    })

                if expires_at is not None:

                    cur.execute("""
                        SELECT NOW() > %s;
                    """, (expires_at,))

                    if cur.fetchone()[0]:
                        return forbidden({
                            "error":
                            "This invitation has expired"
                        })

            # ====================================================
            # ADMIN PATH
            # ====================================================

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

                if relationship is not None:
                    gift_aid_reference = relationship[0]

            # ====================================================
            # MEMBER
            # ====================================================

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

            # ====================================================
            # CURRENT OPERATIONAL MEMBERS
            #
            # This represents the live relationship table.
            # ====================================================

            members = []

            if gift_aid_reference is not None:

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

            # ====================================================
            # MOST RECENT CONFIRMED DECLARATION
            #
            # Pending review records must NOT replace the
            # confirmed declaration shown to the user.
            # ====================================================

            declaration = None

            if gift_aid_reference is not None:

                cur.execute("""
                    SELECT
                        id,
                        member_id,
                        gift_aid_reference,
                        action,
                        declaration_method,
                        declaration_text,
                        declarer_name,
                        declarer_address,
                        email_address,
                        affirmed_date,
                        recorded_at,
                        ip_address,
                        user_agent,
                        invitation_id,
                        recorded_by,
                        wording_version_id,
                        affirmed,
                        status,
                        covered_members
                    FROM gift_aid_declaration_audit
                    WHERE gift_aid_reference = %s
                      AND status = 'CONFIRMED'
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT 1;
                """, (gift_aid_reference,))

                audit_row = cur.fetchone()

                if audit_row is not None:

                    declaration = {
                        "id": audit_row[0],
                        "member_id": audit_row[1],
                        "gift_aid_reference": audit_row[2],
                        "action": audit_row[3],
                        "declaration_method": audit_row[4],
                        "declaration_text": audit_row[5],
                        "declarer_name": audit_row[6],
                        "declarer_address": audit_row[7],
                        "email_address": audit_row[8],
                        "affirmed_date": (
                            audit_row[9].isoformat()
                            if audit_row[9]
                            else None
                        ),
                        "recorded_at": (
                            audit_row[10].isoformat()
                            if audit_row[10]
                            else None
                        ),
                        "ip_address": (
                            str(audit_row[11])
                            if audit_row[11]
                            else None
                        ),
                        "user_agent": audit_row[12],
                        "invitation_id": audit_row[13],
                        "recorded_by": audit_row[14],
                        "wording_version_id": audit_row[15],
                        "affirmed": audit_row[16],
                        "status": audit_row[17],
                        "covered_members": audit_row[18],
                    }

            # ====================================================
            # CURRENT WORDING
            # ====================================================

            cur.execute("""
                SELECT
                    id,
                    version,
                    wording,
                    effective_from,
                    effective_until
                FROM gift_aid_wording_versions
                WHERE effective_from <= CURRENT_DATE
                  AND (
                      effective_until IS NULL
                      OR effective_until >= CURRENT_DATE
                  )
                ORDER BY
                    effective_from DESC,
                    id DESC
                LIMIT 1;
            """)

            wording_row = cur.fetchone()

            if wording_row is None:
                return not_found({
                    "error":
                    "No current Gift Aid wording is available"
                })

            wording = {
                "wording_version_id": wording_row[0],
                "version": wording_row[1],
                "wording": wording_row[2],
                "effective_from": (
                    wording_row[3].isoformat()
                    if wording_row[3]
                    else None
                ),
                "effective_until": (
                    wording_row[4].isoformat()
                    if wording_row[4]
                    else None
                ),
            }

            # ====================================================
            # RETURN
            # ====================================================

            return success({

                "gift_aid_reference":
                    gift_aid_reference,

                "member_id":
                    member_id,

                "invitation_id":
                    invitation_id,

                "member": {
                    "member_id": member[0],
                    "membership_number": member[1],
                    "first_name": member[2],
                    "surname": member[3],
                    "tower": member[4],
                },

                # Live operational relationships
                "members":
                    members,

                # Historical snapshot contained in the declaration
                "covered_members": (
                    declaration["covered_members"]
                    if declaration is not None
                    else []
                ),

                "declaration":
                    declaration,

                "wording":
                    wording,
            })

    finally:

        conn.close()


# =================================================================
# POST
# =================================================================

def handle_post(event, path):

    params = event.get("queryStringParameters") or {}

    # ------------------------------------------------------------
    # Determine access method
    # ------------------------------------------------------------

    if path == PUBLIC_DECLARATION_PATH:

        token = params.get("token")

        if not token:
            return bad_request({
                "error": "token is required"
            })

        member_id = None
        declaration_method = "ONLINE"
        recorded_by = None
        is_token_request = True

    elif path == ADMIN_DECLARATION_PATH:

        member_id_param = params.get("member_id")

        if not member_id_param:
            return bad_request({
                "error": "member_id is required"
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
                "error":
                "Authenticated user identity not available"
            })

        recorded_by = cognito_sub
        token = None
        is_token_request = False

    else:

        return bad_request({
            "error": "Invalid Gift Aid declaration route"
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
    # Declaration data
    # ------------------------------------------------------------

    declarer_name = body.get("declarer_name")
    declarer_address = body.get("declarer_address")
    email_address = body.get("email_address")
    affirmed_date = body.get("affirmed_date")
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

    if not email_address:
        return bad_request({
            "error": "email_address is required"
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
    # Affirmed date
    #
    # For manual paper declarations, the admin can supply the
    # handwritten date. If it is unavailable, use today's date.
    #
    # For ONLINE declarations the client should normally supply
    # the date on which the member affirmed.
    # ------------------------------------------------------------

    if not affirmed_date:

        cur_date = None

        conn_temp = get_connection()

        try:
            with conn_temp.cursor() as cur:
                cur.execute("SELECT CURRENT_DATE")
                cur_date = cur.fetchone()[0].isoformat()
        finally:
            conn_temp.close()

        affirmed_date = cur_date

    # ------------------------------------------------------------
    # Members submitted by the form
    #
    # These are currently member IDs. The Hugo UI will eventually
    # collect names / numbers and the authenticated admin side
    # will resolve them.
    # ------------------------------------------------------------

    submitted_members = body.get("members")

    if submitted_members is None:
        submitted_members = []

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

    # ------------------------------------------------------------
    # COVERED_ELSEWHERE
    #
    # No online relationship is created.
    # The supplied person's description is retained separately.
    # ------------------------------------------------------------

    covered_elsewhere = body.get("covered_elsewhere")

    if action == "COVERED_ELSEWHERE":

        if not covered_elsewhere:
            return bad_request({
                "error":
                "covered_elsewhere is required"
            })

        if not isinstance(covered_elsewhere, str):
            return bad_request({
                "error":
                "covered_elsewhere must be text"
            })

    # ------------------------------------------------------------
    # DECLINED does not require covered members.
    # AFFIRMED / UPDATED require at least one member only if the
    # declaration actually has covered members.
    #
    # The declarer themselves does not need to be submitted because
    # member_id is always the person completing the declaration.
    # ------------------------------------------------------------

    if action in {"AFFIRMED", "UPDATED"} and not submitted_members:

        # It is legitimate for the declarer to have no dependents.
        # Therefore an empty list is permitted.
        pass

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
            existing_declaration = None

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
                        "error":
                        "This invitation has already been used"
                    })

                if expires_at is not None:

                    cur.execute(
                        "SELECT NOW() > %s",
                        (expires_at,)
                    )

                    if cur.fetchone()[0]:
                        return forbidden({
                            "error":
                            "This invitation has expired"
                        })

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
                            "error":
                            "Invalid gift_aid_reference"
                        })

                    if requested_reference <= 0:

                        return bad_request({
                            "error":
                            "Invalid gift_aid_reference"
                        })

                    gift_aid_reference = requested_reference
                    reference_supplied = True

                else:

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
                        affirmed_date,
                    ))

                    relationship = cur.fetchone()

                    if relationship is not None:
                        gift_aid_reference = relationship[0]

            # ====================================================
            # FIND EXISTING CONFIRMED DECLARATION
            # ====================================================

            if gift_aid_reference is not None:

                cur.execute("""
                    SELECT
                        id,
                        member_id,
                        gift_aid_reference,
                        action,
                        declaration_method,
                        declaration_text,
                        declarer_name,
                        declarer_address,
                        email_address,
                        affirmed_date,
                        recorded_at,
                        wording_version_id,
                        affirmed,
                        status,
                        covered_members
                    FROM gift_aid_declaration_audit
                    WHERE gift_aid_reference = %s
                      AND status = 'CONFIRMED'
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT 1
                """, (gift_aid_reference,))

                existing_declaration = cur.fetchone()

                declaration_exists = (
                    existing_declaration is not None
                )

            # ====================================================
            # ONLINE CREATE
            # ====================================================

            if (
                is_token_request
                and gift_aid_reference is None
            ):

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

                if not reference_supplied:

                    return bad_request({
                        "error":
                        "gift_aid_reference is required for a new paper declaration"
                    })

                if action != "AFFIRMED":

                    return bad_request({
                        "error":
                        "A new declaration must use action AFFIRMED"
                    })

            # ====================================================
            # CONFIRM MEMBER EXISTS
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
            # CURRENT MEMBERS
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
                    affirmed_date,
                ))

                existing_members = {
                    row[0]
                    for row in cur.fetchall()
                }

            # ====================================================
            # VALIDATE SUBMITTED MEMBER IDS
            #
            # Only an authenticated admin can have IDs resolved
            # against the members database.
            #
            # Tokenised users cannot search the members database,
            # so their submitted member IDs are treated as
            # unverified and cause pending review.
            # ====================================================

            invalid_members = set()

            if submitted_members:

                if is_token_request:

                    # Token users cannot prove these IDs correspond
                    # to the intended people.
                    pending_member_changes = True

                else:

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

                    pending_member_changes = False

            else:

                pending_member_changes = False

            # ====================================================
            # DETERMINE MEMBER CHANGES
            # ====================================================

            if action == "CANCELLED":

                added_members = set()
                removed_members = existing_members

            elif action in {
                "DECLINED",
                "COVERED_ELSEWHERE",
            }:

                added_members = set()
                removed_members = set()

            else:

                added_members = (
                    submitted_members
                    - existing_members
                )

                removed_members = (
                    existing_members
                    - submitted_members
                )

            member_changes = bool(
                added_members or removed_members
            )

            # ====================================================
            # DETERMINE STATUS
            # ====================================================

            if action == "COVERED_ELSEWHERE":

                audit_status = "PENDING_REVIEW"

            elif (
                is_token_request
                and member_changes
            ):

                audit_status = "PENDING_REVIEW"

            else:

                audit_status = "CONFIRMED"

            # ====================================================
            # DETERMINE AFFIRMED FLAG
            # ====================================================

            if action in {
                "DECLINED",
                "COVERED_ELSEWHERE",
            }:

                audit_affirmed = False

            elif audit_status == "PENDING_REVIEW":

                audit_affirmed = False

            else:

                audit_affirmed = True

            # ====================================================
            # DETERMINE AUDIT ACTION
            # ====================================================

            if action == "DECLINED":

                audit_action = "DECLINED"

            elif action == "COVERED_ELSEWHERE":

                audit_action = "COVERED_ELSEWHERE"

            elif not declaration_exists:

                audit_action = "AFFIRMED"

            elif action == "CANCELLED":

                audit_action = "CANCELLED"

            else:

                audit_action = "UPDATED"

            # ====================================================
            # COVERED MEMBERS SNAPSHOT
            #
            # For a pending token update, retain the user's
            # complete proposed list.
            #
            # For a normal confirmed declaration, this is also
            # the complete declaration snapshot.
            # ====================================================

            covered_members = []

            if action not in {
                "DECLINED",
                "COVERED_ELSEWHERE",
                "CANCELLED",
            }:

                if submitted_members:

                    cur.execute("""
                        SELECT
                            id,
                            membership_number,
                            first_name,
                            surname
                        FROM members
                        WHERE id = ANY(%s)
                        ORDER BY surname, first_name
                    """, (
                        list(submitted_members),
                    ))

                    covered_members = [
                        {
                            "member_id": row[0],
                            "membership_number": row[1],
                            "first_name": row[2],
                            "surname": row[3],
                        }
                        for row in cur.fetchall()
                    ]

                else:

                    covered_members = []

            elif action == "CANCELLED":

                if existing_members:

                    cur.execute("""
                        SELECT
                            id,
                            membership_number,
                            first_name,
                            surname
                        FROM members
                        WHERE id = ANY(%s)
                        ORDER BY surname, first_name
                    """, (
                        list(existing_members),
                    ))

                    covered_members = [
                        {
                            "member_id": row[0],
                            "membership_number": row[1],
                            "first_name": row[2],
                            "surname": row[3],
                        }
                        for row in cur.fetchall()
                    ]

            # ====================================================
            # UPDATE OPERATIONAL RELATIONSHIPS
            #
            # Only confirmed declarations alter gift_aid_members.
            # Pending token submissions do not.
            # ====================================================

            if audit_status == "CONFIRMED":

                # ------------------------------------------------
                # ADD
                # ------------------------------------------------

                for new_member_id in added_members:

                    cur.execute("""
                        INSERT INTO gift_aid_members (
                            member_id,
                            gift_aid_reference,
                            valid_until
                        )
                        VALUES (%s, %s, NULL)
                        ON CONFLICT (member_id, gift_aid_reference)
                        DO UPDATE SET valid_until = NULL;
                    """, (
                        new_member_id,
                        gift_aid_reference,
                    ))

                # ------------------------------------------------
                # REMOVE
                # ------------------------------------------------

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
                        affirmed_date,
                        gift_aid_reference,
                        removed_member_id,
                        affirmed_date,
                    ))

            # ====================================================
            # RECORD WHO SUBMITTED
            # ====================================================

            if is_token_request:

                recorded_by = str(member_id)

            # ====================================================
            # RECORD COVERED ELSEWHERE IN SNAPSHOT
            # ====================================================

            if action == "COVERED_ELSEWHERE":

                covered_members = [
                    {
                        "description":
                            covered_elsewhere
                    }
                ]

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
                    affirmed_date,
                    ip_address,
                    user_agent,
                    invitation_id,
                    recorded_by,
                    wording_version_id,
                    affirmed,
                    status,
                    covered_members
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
                affirmed_date,
                get_source_ip(event),
                get_user_agent(event),
                invitation_id,
                recorded_by,
                wording_version_id,
                audit_affirmed,
                audit_status,
                json.dumps(covered_members),
            ))

            audit_id = cur.fetchone()[0]

            # ====================================================
            # COMPLETE ONLINE INVITATION
            #
            # Only consume the invitation when the submission is
            # actually accepted as the response.
            #
            # A pending review still counts as an answered
            # invitation, so it is consumed here too.
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

                "affirmed":
                    audit_affirmed,

                "status":
                    audit_status,

                "affirmed_date":
                    affirmed_date,

                "covered_members":
                    covered_members,

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