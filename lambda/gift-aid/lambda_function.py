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

from giftaid1 import (
     handle_resolve_coverage,
     handle_resolve_member,
     handle_confirm_relationships,
     handle_dashboard_summary
)

from ga_email import (
    send_email,
    send_gift_aid_submission_email,
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
PENDING_REVIEW_PATH = "/api/gift-aid/admin/pending"
RESOLVE_MEMBER_PATH = "/api/gift-aid/admin/pending"
CONFIRM_RELATIONSHIPS_PATH = "/api/gift-aid/admin/pending"
RESOLVE_COVERAGE_PATH = "/api/gift-aid/admin/pending"
EMAIL_TEST_PATH = "/api/gift-aid/email-test"
DASHBOARD_SUMMARY_PATH = "/api/gift-aid/admin/dashboard"


def get_user_groups(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    groups = claims.get("cognito:groups", [])

    if isinstance(groups, str):
        return [groups]

    return groups or []


def get_cognito_sub(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    return claims.get("sub")


def can_administer(event):
    groups = set(get_user_groups(event))

    return bool(
        groups.intersection(ALLOWED_ADMIN_GROUPS)
    )


def hash_token(token):
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def get_source_ip(event):
    request_context = event.get(
        "requestContext",
        {}
    )

    http = request_context.get(
        "http",
        {}
    )

    return http.get("source")


def get_user_agent(event):
    headers = event.get(
        "headers",
        {}
    )

    if not headers:
        return None

    for key, value in headers.items():

        if key.lower() == "user-agent":
            return value

    return None


def get_request_path(event):
    request_context = event.get(
        "requestContext",
        {}
    )

    http = request_context.get(
        "http",
        {}
    )

    path = http.get("path")

    if path:
        return path

    return event.get(
        "rawPath"
    )


def covered_member_ids(covered_members):
    ids = set()

    for member in covered_members or []:

        if not isinstance(member, dict):
            continue

        member_id = member.get(
            "member_id"
        )

        if member_id is None:
            continue

        try:
            ids.add(
                int(member_id)
            )

        except (
            TypeError,
            ValueError
        ):
            continue

    return ids


def covered_members_have_informal_entries(
    covered_members
):
    for member in covered_members or []:

        if not isinstance(member, dict):
            continue

        if member.get("member_id") is None:
            return True

    return False


def declaration_relationships_consistent(
    declaration,
    existing_members
):
    if declaration is None:
        return True, None

    action = declaration[3]

    covered_members = (
        declaration[16]
        or []
    )

    live_ids = {
        int(member["member_id"])
        for member in existing_members
    }

    snapshot_ids = covered_member_ids(
        covered_members
    )

    # The declaration owner is also a Gift Aid relationship.
    owner_id = declaration[1]

    if owner_id is not None:
        snapshot_ids.add(
            int(owner_id)
        )

    if action in (
        "CANCELLED",
        "DECLINED",
        "COVERED_ELSEWHERE",
    ):

        if live_ids:
            return (
                False,
                "The declaration is no longer active but live Gift Aid relationships remain."
            )

        return True, None

    if covered_members_have_informal_entries(
        covered_members
    ):

        return (
            False,
            "Confirmed declaration contains covered members which cannot be resolved to member IDs."
        )

    if snapshot_ids != live_ids:

        return (
            False,
            "The declaration covered-member list does not match the current Gift Aid relationships."
        )

    return True, None


def lambda_handler(event, context):

    path = get_request_path(
        event
    )

    method = event.get(
        "requestContext",
        {}
    ).get(
        "http",
        {}
    ).get(
        "method",
        ""
    ).upper()
    
        # Email test
    if path == EMAIL_TEST_PATH:

        if method != "POST":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to send test emails"
            )

        body_text = (
            event.get("body")
            or "{}"
        )

        try:

            body = json.loads(
                body_text
            )

        except json.JSONDecodeError:

            return bad_request(
                "Invalid JSON request body"
            )

        recipient = body.get(
            "to"
        )

        if not recipient:

            return bad_request(
                "Recipient is required"
            )

        try:

            send_email(
                recipient=recipient,
                subject="Suffolk Guild Gift Aid email test",
                body=(
                    "This is a test email from the "
                    "Suffolk Guild of Ringers Gift Aid system."
                ),
            )

        except Exception as exc:

            return bad_request(
                f"Email could not be sent: {str(exc)}"
            )

        return success(
            {
                "message": "Test email sent",
                "to": recipient,
            }
        )

    # Process 1: resolve an informal covered member
    resolve_prefix = (
        RESOLVE_MEMBER_PATH + "/"
    )

    if (
        path.startswith(resolve_prefix)
        and
        path.endswith("/resolve-member")
    ):

        if method != "POST":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to resolve Gift Aid reviews"
            )

        audit_id_text = path[
            len(resolve_prefix):
        ]

        audit_id_text = audit_id_text[
            :-len("/resolve-member")
        ]

        return handle_resolve_member(
            event,
            audit_id_text
        )

    # Process 2: confirm a relationship mismatch
    confirm_prefix = (
        CONFIRM_RELATIONSHIPS_PATH + "/"
    )

    if (
        path.startswith(confirm_prefix)
        and
        path.endswith("/confirm-relationships")
    ):

        if method != "POST":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to confirm Gift Aid relationships"
            )

        audit_id_text = path[
            len(confirm_prefix):
        ]

        audit_id_text = audit_id_text[
            :-len("/confirm-relationships")
        ]

        return handle_confirm_relationships(
            event,
            audit_id_text
        )

    # Process 3: resolve a COVERED_ELSEWHERE coverage request
    coverage_prefix = (
        RESOLVE_COVERAGE_PATH + "/"
    )

    if (
        path.startswith(coverage_prefix)
        and
        path.endswith("/resolve-coverage")
    ):

        if method != "POST":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to resolve Gift Aid coverage requests"
            )

        audit_id_text = path[
            len(coverage_prefix):
        ]

        audit_id_text = audit_id_text[
            :-len("/resolve-coverage")
        ]

        return handle_resolve_coverage(
            event,
            audit_id_text
        )

    if path == PENDING_REVIEW_PATH:

        if method != "GET":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to view Gift Aid pending reviews"
            )

        return handle_pending()

    # Gift Aid dashboard summary

    if path == DASHBOARD_SUMMARY_PATH:

        if method != "GET":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to view the Gift Aid dashboard"
            )

        return handle_dashboard_summary()


    # original handling for public & admin declaration management
    
    if path not in (
        PUBLIC_DECLARATION_PATH,
        ADMIN_DECLARATION_PATH,
    ):

        return not_found(
            "Not found"
        )

    is_public = (
        path ==
        PUBLIC_DECLARATION_PATH
    )

    is_admin = (
        path ==
        ADMIN_DECLARATION_PATH
    )

    query_parameters = (
        event.get(
            "queryStringParameters"
        )
        or {}
    )

    token = query_parameters.get(
        "token"
    )

    member_id_parameter = (
        query_parameters.get(
            "member_id"
        )
    )

    if is_public:

        if method not in (
            "GET",
            "POST",
        ):

            return bad_request(
                "Method not allowed"
            )

        if not token:

            return bad_request(
                "Invitation token is required"
            )

        if member_id_parameter:

            return bad_request(
                "member_id is not permitted on the public declaration endpoint"
            )

    if is_admin:

        if method not in (
            "GET",
            "POST",
        ):

            return bad_request(
                "Method not allowed"
            )

        if not member_id_parameter:

            return bad_request(
                "member_id is required"
            )

        if token:

            return bad_request(
                "token is not permitted on the admin declaration endpoint"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to administer Gift Aid declarations"
            )

    if method == "GET":

        return handle_get(
            event,
            is_public,
            token,
            member_id_parameter,
        )

    if method == "POST":

        return handle_post(
            event,
            is_public,
            token,
            member_id_parameter,
        )

    return bad_request(
        "Unsupported method"
    )


def handle_pending():

    conn = None

    try:

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                COUNT(*)
            FROM gift_aid_declaration_audit a
            WHERE a.status = 'PENDING_REVIEW'
              AND NOT EXISTS (
                  SELECT 1
                  FROM gift_aid_declaration_audit newer
                  WHERE newer.supersedes_audit_id = a.id
              )
            """
        )

        total_pending = (
            cur.fetchone()[0]
        )

        cur.execute(
            """
            SELECT
                a.pending_review_type,
                COUNT(*)
            FROM gift_aid_declaration_audit a
            WHERE a.status = 'PENDING_REVIEW'
              AND NOT EXISTS (
                  SELECT 1
                  FROM gift_aid_declaration_audit newer
                  WHERE newer.supersedes_audit_id = a.id
              )
            GROUP BY a.pending_review_type
            """
        )

        rows = cur.fetchall()

        counts = {
            "UNRESOLVED_MEMBER": 0,
            "RELATIONSHIP_MISMATCH": 0,
            "COVERAGE_REQUEST": 0,
        }

        for row in rows:

            review_type = row[0]
            count = row[1]

            if review_type in counts:

                counts[review_type] = count

        return success(
            {
                "total": total_pending,
                "types": counts,
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid pending review error:",
            exc
        )

        return bad_request(
            "Unable to load pending Gift Aid reviews"
        )

    finally:

        if conn:
            conn.close()


def handle_get(
    event,
    is_public,
    token,
    member_id_parameter,
):

    conn = None

    try:

        conn = get_connection()

        cur = conn.cursor()

        invitation_id = None

        if is_public:

            token_hash = hash_token(
                token
            )

            cur.execute(
                """
                SELECT
                    id,
                    member_id,
                    gift_aid_reference,
                    expires_at,
                    used_at
                FROM gift_aid_invitations
                WHERE token_hash = %s
                """,
                (
                    token_hash,
                ),
            )

            invitation = cur.fetchone()

            if not invitation:

                return not_found(
                    "Invalid Gift Aid invitation"
                )

            invitation_id = invitation[0]

            member_id = invitation[1]

            gift_aid_reference = (
                invitation[2]
            )

            expires_at = invitation[3]

            used_at = invitation[4]

            if used_at is not None:

                return bad_request(
                    "This Gift Aid invitation has already been used"
                )

            cur.execute(
                "SELECT CURRENT_TIMESTAMP"
            )

            current_time = cur.fetchone()[0]

            if expires_at is not None and (
                expires_at <= current_time
            ):

                return bad_request(
                    "This Gift Aid invitation has expired"
                )

        else:

            try:

                member_id = int(
                    member_id_parameter
                )

            except (
                TypeError,
                ValueError
            ):

                return bad_request(
                    "Invalid member_id"
                )

            cur.execute(
                """
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
                """,
                (
                    member_id,
                ),
            )

            reference_row = (
                cur.fetchone()
            )

            gift_aid_reference = (
                reference_row[0]
                if reference_row
                else None
            )

        cur.execute(
            """
            SELECT
                id,
                membership_number,
                first_name,
                surname,
                tower_id
            FROM members
            WHERE id = %s
            """,
            (
                member_id,
            ),
        )

        member_row = cur.fetchone()

        if not member_row:

            return not_found(
                "Member not found"
            )

        member = {
            "member_id": member_row[0],
            "membership_number": member_row[1],
            "first_name": member_row[2],
            "surname": member_row[3],
            "tower_id": member_row[4]
        }

        cur.execute(
            """
            SELECT
                gam.member_id,
                m.membership_number,
                m.first_name,
                m.surname
            FROM gift_aid_members gam
            JOIN members m
                ON m.id = gam.member_id
            WHERE gam.gift_aid_reference = %s
              AND (
                  gam.valid_until IS NULL
                  OR gam.valid_until >= CURRENT_DATE
              )
            ORDER BY gam.member_id
            """,
            (
                gift_aid_reference,
            ),
        )

        live_rows = cur.fetchall()

        members = []

        for row in live_rows:

            members.append(
                {
                    "member_id": row[0],
                    "membership_number": row[1],
                    "first_name": row[2],
                    "surname": row[3],
                }
            )

        cur.execute(
            """
            SELECT
                id,
                member_id,
                gift_aid_reference,
                action,
                declaration_method,
                declaration_text,
                declarer_name,
                declarer_address_line_1,
                declarer_address_line_2,
                declarer_postcode,
                email_address,
                affirmed_date,
                recorded_at,
                invitation_id,
                recorded_by,
                wording_version_id,
                covered_members,
                affirmed,
                status
            FROM gift_aid_declaration_audit
            WHERE gift_aid_reference = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                gift_aid_reference,
            ),
        )

        declaration_row = (
            cur.fetchone()
        )

        declaration = None

        covered_members = []

        if declaration_row:

            declaration = {
                "id": declaration_row[0],
                "member_id": declaration_row[1],
                "gift_aid_reference": declaration_row[2],
                "action": declaration_row[3],
                "declaration_method": declaration_row[4],
                "declaration_text": declaration_row[5],
                "declarer_name": declaration_row[6],
                "declarer_address_line_1": declaration_row[7],
                "declarer_address_line_2": declaration_row[8],
                "declarer_postcode": declaration_row[9],
                "email_address": declaration_row[10],
                "affirmed_date": (
                    declaration_row[11].isoformat()
                    if declaration_row[11]
                    else None
                ),
                "recorded_at": (
                    declaration_row[12].isoformat()
                    if declaration_row[12]
                    else None
                ),
                "invitation_id": declaration_row[13],
                "recorded_by": declaration_row[14],
                "wording_version_id": declaration_row[15],
                "covered_members": declaration_row[16] or [],
                "affirmed": declaration_row[17],
                "status": declaration_row[18],
            }

            covered_members = (
                declaration_row[16]
                or []
            )

        cur.execute(
            """
            SELECT
                id,
                version,
                wording,
                effective_from
            FROM gift_aid_wording_versions
            WHERE id = COALESCE(
                %s,
                (
                    SELECT id
                    FROM gift_aid_wording_versions
                    ORDER BY id DESC
                    LIMIT 1
                )
            )
            """,
            (
                declaration["wording_version_id"]
                if declaration
                else None,
            ),
        )

        wording_row = cur.fetchone()

        wording = None

        if wording_row:

            wording = {
                "wording_version_id": wording_row[0],
                "version": wording_row[1],
                "wording": wording_row[2],
                "effective_from": (
                    wording_row[3].isoformat()
                    if wording_row[3]
                    else None
                ),
            }

        return success(
            {
                "gift_aid_reference": gift_aid_reference,
                "member_id": member_id,
                "invitation_id": invitation_id,
                "member": member,
                "members": members,
                "covered_members": covered_members,
                "declaration": declaration,
                "wording": wording,
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid GET error:",
            exc
        )

        return bad_request(
            "Unable to load the Gift Aid declaration"
        )

    finally:

        if conn:
            conn.close()


def handle_post(
    event,
    is_public,
    token,
    member_id_parameter,
):

    conn = None

    try:

        if is_public:

            method = "ONLINE"
            member_id = None
            recorded_by = None
            is_token_request = True

        else:

            method = "MANUAL"
            is_token_request = False

            try:

                member_id = int(
                    member_id_parameter
                )

            except (
                TypeError,
                ValueError
            ):

                return bad_request(
                    "Invalid member_id"
                )

            recorded_by = get_cognito_sub(
                event
            )

        body_text = (
            event.get("body")
            or "{}"
        )

        try:

            body = json.loads(
                body_text
            )

        except json.JSONDecodeError:

            return bad_request(
                "Invalid JSON request body"
            )

        action = body.get(
            "action"
        )

        if action not in VALID_ACTIONS:

            return bad_request(
                "Invalid Gift Aid action"
            )

        follow_up_action = body.get(
            "follow_up_action"
        )

        if follow_up_action:

            if not (
                action == "CANCELLED"
                and follow_up_action ==
                "COVERED_ELSEWHERE"
            ):

                return bad_request(
                    "Invalid follow-up action"
                )

        declarer_name = body.get(
            "declarer_name"
        )

        address_line_1 = body.get(
            "declarer_address_line_1"
        )

        address_line_2 = body.get(
            "declarer_address_line_2"
        )

        postcode = body.get(
            "declarer_postcode"
        )

        email_address = body.get(
            "email_address"
        )

        affirmed_date = body.get(
            "affirmed_date"
        )

        wording_version_id = body.get(
            "wording_version_id"
        )

        declaration_text = body.get(
            "declaration_text"
        )

        affirmed = body.get(
            "affirmed"
        )

        if action in (
            "AFFIRMED",
            "UPDATED",
        ):

            required_fields = {
                "declarer_name": declarer_name,
                "declarer_address_line_1": address_line_1,
                "declarer_postcode": postcode,
                "email_address": email_address,
                "wording_version_id": wording_version_id,
                "declaration_text": declaration_text,
            }

            for field_name, value in required_fields.items():

                if value is None or str(value).strip() == "":

                    return bad_request(
                        field_name +
                        " is required"
                    )

            if affirmed is not True:

                return bad_request(
                    "Affirmation is required"
                )

        else:

            if affirmed is None:

                affirmed = False

            if action in (
                "CANCELLED",
                "DECLINED",
                "COVERED_ELSEWHERE",
            ):

                if affirmed is not False:

                    return bad_request(
                        "This action cannot be affirmed"
                    )

                address_line_1 = (
                    address_line_1
                    or None
                )

                address_line_2 = (
                    address_line_2
                    or None
                )

                postcode = (
                    postcode
                    or None
                )

                email_address = (
                    email_address
                    or None
                )

        if not affirmed_date:

            affirmed_date = (
                "CURRENT_DATE"
            )

        submitted_members = body.get(
            "members"
        )

        if submitted_members is None:

            submitted_members = []

        if not isinstance(
            submitted_members,
            list
        ):

            return bad_request(
                "members must be a list"
            )

        submitted_covered_members = body.get(
            "covered_members"
        )

        if submitted_covered_members is None:

            submitted_covered_members = []

        if not isinstance(
            submitted_covered_members,
            list
        ):

            return bad_request(
                "covered_members must be a list"
            )

        for item in submitted_covered_members:

            if not isinstance(
                item,
                dict
            ):

                return bad_request(
                    "Each covered member must be an object"
                )

            if not (
                item.get("membership_number")
                or item.get("name")
                or item.get("member_id")
            ):

                return bad_request(
                    "Each covered member must contain a membership number, name or member_id"
                )

        if is_public:

            for item in submitted_covered_members:

                if item.get("member_id") is not None:

                    try:
                        int(
                            item["member_id"]
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        return bad_request(
                            "Invalid covered member_id"
                        )

            if submitted_members:

                return bad_request(
                    "members cannot be supplied on the public declaration endpoint"
                )

        covered_elsewhere = body.get(
            "covered_elsewhere"
        )

        if action == "COVERED_ELSEWHERE":

            if not covered_elsewhere:

                return bad_request(
                    "covered_elsewhere information is required"
                )

        conn = get_connection()

        cur = conn.cursor()

        invitation_id = None

        # This is the audit row which the new row will supersede.
        # It remains NULL when this is the first audit version.
        supersedes_audit_id = None

        if is_public:

            token_hash = hash_token(
                token
            )

            cur.execute(
                """
                SELECT
                    id,
                    member_id,
                    gift_aid_reference,
                    expires_at,
                    used_at
                FROM gift_aid_invitations
                WHERE token_hash = %s
                FOR UPDATE
                """,
                (
                    token_hash,
                ),
            )

            invitation = cur.fetchone()

            if not invitation:

                return not_found(
                    "Invalid Gift Aid invitation"
                )

            invitation_id = invitation[0]

            member_id = invitation[1]

            gift_aid_reference = (
                invitation[2]
            )

            expires_at = invitation[3]

            used_at = invitation[4]

            if used_at is not None:

                return bad_request(
                    "This Gift Aid invitation has already been used"
                )

            cur.execute(
                "SELECT CURRENT_TIMESTAMP"
            )

            current_time = cur.fetchone()[0]

            if expires_at is not None and (
                expires_at <= current_time
            ):

                return bad_request(
                    "This Gift Aid invitation has expired"
                )

            if (
                action == "COVERED_ELSEWHERE"
                and follow_up_action is None
                and gift_aid_reference is not None
            ):

                cur.execute(
                    """
                    SELECT
                        id
                    FROM gift_aid_declaration_audit
                    WHERE invitation_id = %s
                      AND action = 'CANCELLED'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        invitation_id,
                    ),
                )

                cancellation = (
                    cur.fetchone()
                )

                if cancellation is None:

                    return bad_request(
                        "Covered Elsewhere must follow the cancellation of the current declaration"
                    )

                # COVERED_ELSEWHERE has no Gift Aid reference of
                # its own, so its predecessor is the cancellation
                # audit row associated with this invitation.
                supersedes_audit_id = (
                    cancellation[0]
                )

        else:

            supplied_reference = body.get(
                "gift_aid_reference"
            )

            if supplied_reference is not None:

                try:

                    gift_aid_reference = int(
                        supplied_reference
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return bad_request(
                        "Invalid gift_aid_reference"
                    )

            else:

                cur.execute(
                    """
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
                    """,
                    (
                        member_id,
                    ),
                )

                reference_row = (
                    cur.fetchone()
                )

                gift_aid_reference = (
                    reference_row[0]
                    if reference_row
                    else None
                )

        # For declarations which have a Gift Aid reference, the
        # predecessor is the latest audit version for that reference.
        #
        # COVERED_ELSEWHERE is handled separately above because its
        # reference may be NULL.
        if (
            gift_aid_reference is not None
            and supersedes_audit_id is None
        ):

            cur.execute(
                """
                SELECT
                    id
                FROM gift_aid_declaration_audit
                WHERE gift_aid_reference = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    gift_aid_reference,
                ),
            )

            latest_audit_row = (
                cur.fetchone()
            )

            if latest_audit_row:

                supersedes_audit_id = (
                    latest_audit_row[0]
                )

        cur.execute(
            """
            SELECT
                id,
                member_id,
                gift_aid_reference,
                action,
                declaration_method,
                declaration_text,
                declarer_name,
                declarer_address_line_1,
                declarer_address_line_2,
                declarer_postcode,
                email_address,
                affirmed_date,
                recorded_at,
                invitation_id,
                recorded_by,
                wording_version_id,
                covered_members,
                affirmed,
                status
            FROM gift_aid_declaration_audit
            WHERE gift_aid_reference = %s
              AND status = 'CONFIRMED'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                gift_aid_reference,
            ),
        )

        declaration = (
            cur.fetchone()
        )

        declaration_exists = (
            declaration is not None
        )

        if (
            is_public
            and gift_aid_reference is None
            and action in (
                "AFFIRMED",
                "UPDATED",
            )
        ):

            cur.execute(
                """
                SELECT nextval(
                    'gift_aid_reference_seq'
                )
                """
            )

            gift_aid_reference = (
                cur.fetchone()[0]
            )

            # This is a genuinely new declaration reference,
            # so there is no predecessor for this reference.
            if action in (
                "AFFIRMED",
                "UPDATED",
            ):

                supersedes_audit_id = None

        if (
            action in (
                "CANCELLED",
                "DECLINED",
                "COVERED_ELSEWHERE",
            )
            and declaration
        ):

            if not declarer_name:
                declarer_name = declaration[6]

            if not address_line_1:
                address_line_1 = declaration[7]

            if not address_line_2:
                address_line_2 = declaration[8]

            if not postcode:
                postcode = declaration[9]

            if not email_address:
                email_address = declaration[10]

            if not wording_version_id:
                wording_version_id = declaration[15]

            if not declaration_text:
                declaration_text = declaration[5]

        if not declarer_name:

            cur.execute(
                """
                SELECT
                    first_name,
                    surname
                FROM members
                WHERE id = %s
                """,
                (
                    member_id,
                ),
            )

            member_row = (
                cur.fetchone()
            )

            if not member_row:

                return not_found(
                    "Member not found"
                )

            declarer_name = (
                str(member_row[0] or "")
                + " "
                + str(member_row[1] or "")
            ).strip()

        if not wording_version_id:

            cur.execute(
                """
                SELECT id
                FROM gift_aid_wording_versions
                ORDER BY id DESC
                LIMIT 1
                """
            )

            wording_row = (
                cur.fetchone()
            )

            if wording_row:

                wording_version_id = (
                    wording_row[0]
                )

        if action == "CANCELLED":

            declaration_text = (
                declaration_text
                or
                "Gift Aid declaration cancelled."
            )

        elif action == "DECLINED":

            declaration_text = (
                declaration_text
                or
                "Member declined to make a Gift Aid declaration."
            )

        elif action == "COVERED_ELSEWHERE":

            declaration_text = (
                declaration_text
                or
                "Member has indicated that their Gift Aid is covered by another person's declaration."
            )

        if (
            not is_public
            and not declaration_exists
            and action != "AFFIRMED"
        ):

            return bad_request(
                "An admin declaration must be affirmed when creating a new declaration"
            )

        if (
            not is_public
            and not declaration_exists
            and not gift_aid_reference
        ):

            return bad_request(
                "gift_aid_reference is required when creating a new declaration"
            )

        cur.execute(
            """
            SELECT
                id
            FROM members
            WHERE id = %s
            """,
            (
                member_id,
            ),
        )

        if not cur.fetchone():

            return not_found(
                "Member not found"
            )

        cur.execute(
            """
            SELECT
                gam.member_id,
                m.membership_number,
                m.first_name,
                m.surname
            FROM gift_aid_members gam
            JOIN members m
                ON m.id = gam.member_id
            WHERE gam.gift_aid_reference = %s
              AND (
                  gam.valid_until IS NULL
                  OR gam.valid_until >= CURRENT_DATE
              )
            ORDER BY gam.member_id
            """,
            (
                gift_aid_reference,
            ),
        )

        existing_rows = (
            cur.fetchall()
        )

        existing_members = []

        for row in existing_rows:

            existing_members.append(
                {
                    "member_id": row[0],
                    "membership_number": row[1],
                    "first_name": row[2],
                    "surname": row[3],
                }
            )

        state_consistent = True
        inconsistency_reason = None

        if declaration_exists:

            (
                state_consistent,
                inconsistency_reason
            ) = declaration_relationships_consistent(
                declaration,
                existing_members,
            )

        existing_ids = {
            int(member["member_id"])
            for member in existing_members
        }

        submitted_member_ids = set()

        for item in submitted_members:

            if not isinstance(
                item,
                dict
            ):

                return bad_request(
                    "Each member must be an object"
                )

            submitted_id = item.get(
                "member_id"
            )

            if submitted_id is None:

                return bad_request(
                    "Each member must contain member_id"
                )

            try:

                submitted_member_ids.add(
                    int(submitted_id)
                )

            except (
                TypeError,
                ValueError
            ):

                return bad_request(
                    "Invalid member_id"
                )

        for submitted_id in submitted_member_ids:

            cur.execute(
                """
                SELECT
                    id
                FROM members
                WHERE id = %s
                """,
                (
                    submitted_id,
                ),
            )

            if not cur.fetchone():

                return bad_request(
                    "Submitted member does not exist: "
                    + str(submitted_id)
                )

        # These are calculated later, once covered_snapshot has
        # been built.  For CANCELLED the existing live relationships
        # are removed; DECLINED and COVERED_ELSEWHERE do not add or
        # remove relationships here.
        added_members = []
        removed_members = []

        if action == "CANCELLED":

            removed_members = sorted(
                existing_ids
            )

        elif action in (
            "DECLINED",
            "COVERED_ELSEWHERE",
        ):

            added_members = []
            removed_members = []

        covered_snapshot = []

        if action in (
            "AFFIRMED",
            "UPDATED",
        ):

            if "covered_members" in body:

                for item in submitted_covered_members:

                    if not isinstance(
                        item,
                        dict
                    ):
                        continue

                    entry = {}

                    if item.get("member_id") is not None:

                        try:

                            entry["member_id"] = int(
                                item["member_id"]
                            )

                        except (
                            TypeError,
                            ValueError
                        ):
                            pass

                    if item.get(
                        "membership_number"
                    ):

                        entry["membership_number"] = str(
                            item[
                                "membership_number"
                            ]
                        )

                    if item.get(
                        "first_name"
                    ):

                        entry["first_name"] = str(
                            item[
                                "first_name"
                            ]
                        )

                    if item.get(
                        "surname"
                    ):

                        entry["surname"] = str(
                            item[
                                "surname"
                            ]
                        )

                    if item.get(
                        "name"
                    ):

                        entry["name"] = str(
                            item[
                                "name"
                            ]
                        )

                    if entry:

                        covered_snapshot.append(
                            entry
                        )

            elif (
                is_token_request
                and declaration_exists
                and not submitted_members
            ):

                covered_snapshot = (
                    declaration[16]
                    or []
                )

            elif submitted_members:

                for submitted_id in sorted(
                    submitted_member_ids
                ):

                    cur.execute(
                        """
                        SELECT
                            id,
                            membership_number,
                            first_name,
                            surname
                        FROM members
                        WHERE id = %s
                        """,
                        (
                            submitted_id,
                        ),
                    )

                    row = cur.fetchone()

                    if row:

                        covered_snapshot.append(
                            {
                                "member_id": row[0],
                                "membership_number": row[1],
                                "first_name": row[2],
                                "surname": row[3],
                            }
                        )

            elif declaration_exists:

                covered_snapshot = (
                    declaration[16]
                    or []
                )

        elif action == "CANCELLED":

            if declaration_exists:

                covered_snapshot = (
                    declaration[16]
                    or []
                )

            else:

                for member in existing_members:

                    covered_snapshot.append(
                        {
                            "member_id":
                                member["member_id"],
                            "membership_number":
                                member["membership_number"],
                            "first_name":
                                member["first_name"],
                            "surname":
                                member["surname"],
                        }
                    )

        elif action == "COVERED_ELSEWHERE":

            covered_snapshot = [
                {
                    "description":
                        covered_elsewhere
                }
            ]

        # covered_snapshot contains only people OTHER THAN the
        # declaration owner.
        submitted_relationship_ids = (
            covered_member_ids(
                covered_snapshot
            )
        )

        # The declaration owner is also part of the Gift Aid
        # relationship set.
        if member_id is not None:

            submitted_relationship_ids.add(
                int(member_id)
            )

        live_relationship_ids = {
            int(member["member_id"])
            for member in existing_members
        }

        # For an AFFIRMED or UPDATED declaration, the expected
        # relationship set is the owner plus all formal covered
        # members.
        if action in (
            "AFFIRMED",
            "UPDATED",
        ):

            added_members = sorted(
                submitted_relationship_ids -
                live_relationship_ids
            )

            removed_members = sorted(
                live_relationship_ids -
                submitted_relationship_ids
            )

        informal_covered_members = (
            is_token_request
            and
            covered_members_have_informal_entries(
                covered_snapshot
            )
        )

        relationships_match_submission = (
            submitted_relationship_ids ==
            live_relationship_ids
        )

        pending_review_type = None

        if action == "COVERED_ELSEWHERE":

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "COVERAGE_REQUEST"
            )

        elif (
            is_token_request
            and informal_covered_members
        ):

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "UNRESOLVED_MEMBER"
            )

            if not inconsistency_reason:

                inconsistency_reason = (
                    "One or more covered members could not be identified from the declaration."
                )

        elif (
            is_token_request
            and not relationships_match_submission
        ):

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "RELATIONSHIP_MISMATCH"
            )

            if not inconsistency_reason:

                inconsistency_reason = (
                    "The covered members in the submitted declaration do not match the current Gift Aid relationships."
                )

        elif (
            is_token_request
            and added_members
        ):

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "RELATIONSHIP_MISMATCH"
            )

        elif (
            is_token_request
            and removed_members
        ):

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "RELATIONSHIP_MISMATCH"
            )

        elif (
            is_token_request
            and declaration_exists
            and not state_consistent
        ):

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "RELATIONSHIP_MISMATCH"
            )

        else:

            audit_status = (
                "CONFIRMED"
            )

        if action in (
            "DECLINED",
            "CANCELLED",
            "COVERED_ELSEWHERE",
        ):

            audit_affirmed = False

        else:

            audit_affirmed = True

        if action == "DECLINED":

            audit_action = (
                "DECLINED"
            )

        elif action == "COVERED_ELSEWHERE":

            audit_action = (
                "COVERED_ELSEWHERE"
            )

        elif not declaration_exists:

            audit_action = (
                "AFFIRMED"
            )

        elif action == "CANCELLED":

            audit_action = (
                "CANCELLED"
            )

        else:

            audit_action = (
                "UPDATED"
            )

        if (
            audit_status == "CONFIRMED"
        ):

            if added_members:

                for added_id in added_members:

                    cur.execute(
                        """
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
                        """,
                        (
                            added_id,
                            gift_aid_reference,
                        ),
                    )

            if removed_members:

                for removed_id in removed_members:

                    cur.execute(
                        """
                        UPDATE gift_aid_members
                        SET valid_until = %s
                        WHERE member_id = %s
                          AND gift_aid_reference = %s
                          AND (
                              valid_until IS NULL
                              OR valid_until >= %s
                          )
                        """,
                        (
                            affirmed_date
                            if affirmed_date !=
                            "CURRENT_DATE"
                            else None,
                            removed_id,
                            gift_aid_reference,
                            affirmed_date
                            if affirmed_date !=
                            "CURRENT_DATE"
                            else None,
                        ),
                    )

        if is_public:

            recorded_by = str(
                member_id
            )

        if affirmed_date == "CURRENT_DATE":

            affirmed_date_sql = "CURRENT_DATE"

            affirmed_date_value = None

        else:

            affirmed_date_sql = "%s"

            affirmed_date_value = (
                affirmed_date
            )

        if affirmed_date_sql == "%s":

            cur.execute(
                """
                INSERT INTO gift_aid_declaration_audit (
                    member_id,
                    gift_aid_reference,
                    action,
                    declaration_method,
                    declaration_text,
                    declarer_name,
                    declarer_address_line_1,
                    declarer_address_line_2,
                    declarer_postcode,
                    email_address,
                    affirmed_date,
                    ip_address,
                    user_agent,
                    invitation_id,
                    recorded_by,
                    wording_version_id,
                    affirmed,
                    status,
                    pending_review_type,
                    covered_members,
                    supersedes_audit_id
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
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    member_id,
                    gift_aid_reference,
                    audit_action,
                    method,
                    declaration_text,
                    declarer_name,
                    address_line_1,
                    address_line_2,
                    postcode,
                    email_address,
                    affirmed_date_value,
                    get_source_ip(event),
                    get_user_agent(event),
                    invitation_id,
                    recorded_by,
                    wording_version_id,
                    audit_affirmed,
                    audit_status,
                    pending_review_type,
                    json.dumps(
                        covered_snapshot
                    ),
                    supersedes_audit_id,
                ),
            )

        else:

            cur.execute(
                """
                INSERT INTO gift_aid_declaration_audit (
                    member_id,
                    gift_aid_reference,
                    action,
                    declaration_method,
                    declaration_text,
                    declarer_name,
                    declarer_address_line_1,
                    declarer_address_line_2,
                    declarer_postcode,
                    email_address,
                    affirmed_date,
                    ip_address,
                    user_agent,
                    invitation_id,
                    recorded_by,
                    wording_version_id,
                    affirmed,
                    status,
                    pending_review_type,
                    covered_members,
                    supersedes_audit_id
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
                    CURRENT_DATE,
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
                """,
                (
                    member_id,
                    gift_aid_reference,
                    audit_action,
                    method,
                    declaration_text,
                    declarer_name,
                    address_line_1,
                    address_line_2,
                    postcode,
                    email_address,
                    get_source_ip(event),
                    get_user_agent(event),
                    invitation_id,
                    recorded_by,
                    wording_version_id,
                    audit_affirmed,
                    audit_status,
                    pending_review_type,
                    json.dumps(
                        covered_snapshot
                    ),
                    supersedes_audit_id,
                ),
            )

        audit_id = (
            cur.fetchone()[0]
        )

        if is_public:

            keep_invitation_open = (
                action == "CANCELLED"
                and
                follow_up_action ==
                "COVERED_ELSEWHERE"
            )

            if not keep_invitation_open:

                cur.execute(
                    """
                    UPDATE gift_aid_invitations
                    SET used_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        invitation_id,
                    ),
                )

        conn.commit()
        
        
        if email_address:

            try:

                send_gift_aid_submission_email(
                    recipient=email_address,
                    declarer_name=declarer_name,
                    declarer_address_line_1=address_line_1,
                    declarer_address_line_2=address_line_2,
                    declarer_postcode=postcode,                    
                    gift_aid_reference=gift_aid_reference,
                    action=audit_action,
                    status=audit_status,
                    declaration_text=declaration_text,
                    covered_members=covered_snapshot,
                )

            except Exception as exc:

                print(
                    "Gift Aid submission email error:",
                    exc
                )

        response = {
            "gift_aid_reference":
                gift_aid_reference,

            "member_id":
                member_id,

            "invitation_id":
                invitation_id,

            "audit_id":
                audit_id,

            "supersedes_audit_id":
                supersedes_audit_id,

            "action":
                audit_action,

            "method":
                method,

            "affirmed":
                audit_affirmed,

            "status":
                audit_status,

            "affirmed_date":
                affirmed_date
                if affirmed_date !=
                "CURRENT_DATE"
                else None,

            "covered_members":
                covered_snapshot,

            "added_members":
                added_members,

            "removed_members":
                removed_members,
        }

        if (
            audit_status ==
            "PENDING_REVIEW"
            and
            inconsistency_reason
        ):

            response[
                "review_reason"
            ] = inconsistency_reason

        if audit_status == "CONFIRMED":

            return success(
                response
            )

        return success(
            response
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid POST error:",
            exc
        )

        return bad_request(
            "Unable to record the Gift Aid declaration"
        )

    finally:

        if conn:
            conn.close()