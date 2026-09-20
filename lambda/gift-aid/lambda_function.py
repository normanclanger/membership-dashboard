import hashlib
import json
import secrets
from datetime import datetime, timezone, timedelta
import psycopg

from database import get_connection
from responses import (
    success,
    bad_request,
    not_found,
    forbidden,
    created,
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
DECLARATIONS_PATH = "/api/gift-aid/admin/declarations"
ADMIN_SAVE_DECLARATION_PATH = "/api/gift-aid/admin/declaration/save"
ADMIN_EDIT_DECLARATION_PATH = "/api/gift-aid/admin/declaration/edit"
ADMIN_DECLARATION_FOR_MEMBER_PATH = "/api/gift-aid/admin/declaration-for-member"
ADMIN_INVITATION_CHECK_PATH = "/api/gift-aid/admin/invitations/check"
ADMIN_INVITATION_GENERATE_PATH = "/api/gift-aid/admin/invitations/generate"

   
    
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
        
    # Gift Aid declarations list

    if path == DECLARATIONS_PATH:

        if method != "GET":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to view Gift Aid declarations"
            )

        return handle_declarations()
        
    # Save route for admin edited declaration    
    
    if path == ADMIN_SAVE_DECLARATION_PATH:

        if method != "POST":

            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):

            return forbidden(
                "You do not have permission to save Gift Aid declarations"
            )

        return handle_admin_save(event)
        
    if path == ADMIN_EDIT_DECLARATION_PATH:

        if method != "GET":
            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):
            return forbidden(
                "You do not have permission to view Gift Aid declarations"
            )

        return handle_admin_get_declaration(event)

    if path == ADMIN_DECLARATION_FOR_MEMBER_PATH:

        if method != "GET":
            return bad_request("Method not allowed")

        if not can_administer(event):
            return forbidden(
                "You do not have permission to view Gift Aid declarations"
            )

        return handle_admin_get_declaration_for_member(event)
        
    if path == ADMIN_INVITATION_CHECK_PATH:

        if method != "POST":
            return bad_request(
                "Method not allowed"
            )

        if not can_administer(event):
            return forbidden(
                "You do not have permission to check Gift Aid invitations"
            )

        return handle_admin_invitation_check(event)
        
        
    if path == ADMIN_INVITATION_GENERATE_PATH:
        if method != "POST":
            return bad_request("Method not allowed")

        if not can_administer(event):
           return forbidden(
                "You do not have permission to generate Gift Aid invitations"
            )

        return handle_admin_invitation_generate(event)    

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
    
    gift_aid_reference_parameter = (
        query_parameters.get(
            "gift_aid_reference"
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
            
        if not gift_aid_reference_parameter:

            return bad_request(
                "gift_aid_reference is required"
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

            query_parameters = (
                event.get(
                    "queryStringParameters"
                )
                or {}
            )

            gift_aid_reference_parameter = (
                query_parameters.get(
                    "gift_aid_reference"
                )
            )

            try:

                gift_aid_reference = int(
                    gift_aid_reference_parameter
                )

            except (
                TypeError,
                ValueError
            ):

                return bad_request(
                    "Invalid gift_aid_reference"
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
            ORDER BY
                recorded_at DESC,
                id DESC
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
            
def handle_admin_save(event):

    conn = None

    try:

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

        mode = body.get(
            "mode"
        )

        if mode not in (
            "new",
            "edit",
        ):

            return bad_request(
                "mode must be new or edit"
            )

        audit_id = body.get(
            "audit_id"
        )

        if mode == "edit":

            if audit_id is None:

                return bad_request(
                    "audit_id is required when editing a declaration"
                )

            try:

                audit_id = int(
                    audit_id
                )

            except (
                TypeError,
                ValueError
            ):

                return bad_request(
                    "Invalid audit_id"
                )

        else:

            audit_id = None

        member_id = body.get(
            "member_id"
        )

        if member_id is None:

            return bad_request(
                "member_id is required"
            )

        try:

            member_id = int(
                member_id
            )

        except (
            TypeError,
            ValueError
        ):

            return bad_request(
                "Invalid member_id"
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

        required_fields = {
            "declarer_name": declarer_name,
            "declarer_address_line_1": address_line_1,
            "declarer_postcode": postcode,
            "email_address": email_address,
            "wording_version_id": wording_version_id,
            "declaration_text": declaration_text,
        }

        for field_name, value in required_fields.items():

            if (
                value is None
                or
                str(value).strip() == ""
            ):

                return bad_request(
                    field_name
                    + " is required"
                )

        if affirmed is not True:

            return bad_request(
                "Submitting on behalf of the member must be affirmed"
            )

        covered_members = body.get(
            "covered_members"
        )

        if covered_members is None:

            covered_members = []

        if not isinstance(
            covered_members,
            list
        ):

            return bad_request(
                "covered_members must be a list"
            )

        conn = get_connection()

        with conn.cursor() as cur:

            # -------------------------------------------------
            # Verify the declaration owner exists
            # -------------------------------------------------

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
                    member_id,
                ),
            )

            member_row = cur.fetchone()

            if member_row is None:

                return not_found(
                    "Member not found"
                )

            # -------------------------------------------------
            # Validate and build the covered-member snapshot
            # -------------------------------------------------

            covered_snapshot = []

            covered_ids = set()

            for item in covered_members:

                if not isinstance(
                    item,
                    dict
                ):

                    return bad_request(
                        "Each covered member must be an object"
                    )

                submitted_id = item.get(
                    "member_id"
                )

                # Admin Save does not accept unresolved /
                # informal covered members.
                if submitted_id is None:

                    return bad_request(
                        "Every covered member must be resolved to a member_id before saving"
                    )

                try:

                    covered_id = int(
                        submitted_id
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return bad_request(
                        "Invalid covered member_id"
                    )

                if covered_id in covered_ids:

                    return bad_request(
                        "A covered member has been included more than once"
                    )

                covered_ids.add(
                    covered_id
                )

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
                        covered_id,
                    ),
                )

                covered_row = (
                    cur.fetchone()
                )

                if covered_row is None:

                    return bad_request(
                        "Covered member does not exist: "
                        + str(covered_id)
                    )

                covered_snapshot.append(
                    {
                        "member_id":
                            covered_row[0],

                        "membership_number":
                            covered_row[1],

                        "first_name":
                            covered_row[2],

                        "surname":
                            covered_row[3],
                    }
                )

            # A member cannot be both the declaration owner
            # and a covered member.
            if member_id in covered_ids:

                return bad_request(
                    "The declaration owner cannot also be a covered member"
                )

            # -------------------------------------------------
            # Determine current declaration / reference
            # -------------------------------------------------

            current_audit = None
            gift_aid_reference = None
            supersedes_audit_id = None

            if mode == "edit":

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
                        invitation_id,
                        recorded_by,
                        wording_version_id,
                        covered_members,
                        affirmed,
                        status,
                        pending_review_type
                    FROM gift_aid_declaration_audit
                    WHERE id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM gift_aid_declaration_audit newer
                          WHERE newer.supersedes_audit_id = id
                      )
                    FOR UPDATE
                    """,
                    (
                        audit_id,
                    ),
                )

                current_audit = (
                    cur.fetchone()
                )

                if current_audit is None:

                    return not_found(
                        "Current Gift Aid declaration not found"
                    )

                gift_aid_reference = (
                    current_audit[2]
                )

                supersedes_audit_id = (
                    current_audit[0]
                )

                # The member being edited must still be
                # the declaration owner.
                if int(current_audit[1]) != member_id:

                    return bad_request(
                        "The declaration owner does not match the selected member"
                    )

            else:

                # A genuinely new declaration gets a new
                # Gift Aid reference.
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

            # -------------------------------------------------
            # Find current live Gift Aid relationships
            # -------------------------------------------------

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
                        "member_id":
                            row[0],

                        "membership_number":
                            row[1],

                        "first_name":
                            row[2],

                        "surname":
                            row[3],
                    }
                )

            live_relationship_ids = {
                int(member["member_id"])
                for member in existing_members
            }

            # The declaration owner is part of the
            # expected Gift Aid relationship set.
            submitted_relationship_ids = set(
                covered_ids
            )

            submitted_relationship_ids.add(
                member_id
            )

            # -------------------------------------------------
            # Process 1 relationship check
            # -------------------------------------------------

            relationships_match = (
                submitted_relationship_ids
                ==
                live_relationship_ids
            )

            added_members = sorted(
                submitted_relationship_ids
                -
                live_relationship_ids
            )

            removed_members = sorted(
                live_relationship_ids
                -
                submitted_relationship_ids
            )
            
            added_member_details = []
            removed_member_details = []


            for added_member_id in added_members:

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
                    (added_member_id,)
                )

                row = cur.fetchone()

                if row is not None:

                    added_member_details.append({
                        "member_id": row[0],
                        "membership_number": row[1],
                        "first_name": row[2],
                        "surname": row[3]
                    })


            for added_member_id in removed_members:

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
                    (added_member_id,)
                )

                row = cur.fetchone()

                if row is not None:

                    removed_member_details.append({
                        "member_id": row[0],
                        "membership_number": row[1],
                        "first_name": row[2],
                        "surname": row[3]
                    })

            if relationships_match:

                audit_status = (
                        "CONFIRMED"
                    )

                pending_review_type = None

            else:

                audit_status = (
                    "PENDING_REVIEW"
                )

                pending_review_type = (
                    "RELATIONSHIP_MISMATCH"
                )

            # -------------------------------------------------
            # Build the new audit entry
            # -------------------------------------------------

            audit_action = (
                "AFFIRMED"
                if mode == "new"
                else
                "UPDATED"
            )

            recorded_by = get_cognito_sub(
                event
            )

            if not affirmed_date:

                affirmed_date = (
                    "CURRENT_DATE"
                )

            if affirmed_date == "CURRENT_DATE":

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
                        'MANUAL',
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        CURRENT_DATE,
                        %s,
                        %s,
                        NULL,
                        %s,
                        %s,
                        TRUE,
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
                        declaration_text,
                        declarer_name,
                        address_line_1,
                        address_line_2,
                        postcode,
                        email_address,
                        get_source_ip(event),
                        get_user_agent(event),
                        recorded_by,
                        wording_version_id,
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
                        'MANUAL',
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        NULL,
                        %s,
                        %s,
                        TRUE,
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
                        declaration_text,
                        declarer_name,
                        address_line_1,
                        address_line_2,
                        postcode,
                        email_address,
                        affirmed_date,
                        get_source_ip(event),
                        get_user_agent(event),
                        recorded_by,
                        wording_version_id,
                        audit_status,
                        pending_review_type,
                        json.dumps(
                            covered_snapshot
                        ),
                        supersedes_audit_id,
                    ),
                )

            new_audit_id = (
                cur.fetchone()[0]
            )

            conn.commit()

        response = {
            "audit_id":
                new_audit_id,

            "supersedes_audit_id":
                supersedes_audit_id,

            "gift_aid_reference":
                gift_aid_reference,

            "member_id":
                member_id,

            "mode":
                mode,

            "action":
                audit_action,

            "method":
                "MANUAL",

            "affirmed":
                True,

            "status":
                audit_status,

            "pending_review_type":
                pending_review_type,

            "covered_members":
                covered_snapshot,

            "relationship_ids":
                sorted(
                    submitted_relationship_ids
                ),

            "live_relationship_ids":
                sorted(
                    live_relationship_ids
                ),

            "relationships_match":
                relationships_match,

            "added_members":
                added_members,

            "removed_members":
                removed_members,
                
            "added_member_details": added_member_details,
            "removed_member_details": removed_member_details,    
        }

        return success(
            response
        )

    except Exception as exc:

        if conn:

            conn.rollback()

        print(
            "Gift Aid admin save error:",
            exc
        )

        return bad_request(
            "Unable to save the Gift Aid declaration"
        )

    finally:

        if conn:

            conn.close()
            
            
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

def handle_resolve_coverage(
    event,
    audit_id
):

    conn = None

    try:

        try:

            audit_id = int(
                audit_id
            )

        except (
            TypeError,
            ValueError
        ):

            return bad_request(
                "Invalid audit_id"
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

        resolutions = body.get(
            "resolutions"
        )

        if not isinstance(
            resolutions,
            list
        ):

            return bad_request(
                "resolutions must be a list"
            )

        if len(resolutions) != 1:

            return bad_request(
                "Exactly one covered member must be resolved"
            )

        add_requester = body.get(
            "add_requester"
        )

        if add_requester is not True:
            return bad_request(
                "Confirmation is required before adding the requesting member"
            )

        conn = get_connection()

        cur = conn.cursor()

        # Lock the current COVERAGE_REQUEST row.
        cur.execute(
            """
            SELECT
                a.id,
                a.member_id,
                a.gift_aid_reference,
                a.action,
                a.declaration_method,
                a.declaration_text,
                a.declarer_name,
                a.declarer_address_line_1,
                a.declarer_address_line_2,
                a.declarer_postcode,
                a.email_address,
                a.affirmed_date,
                a.invitation_id,
                a.recorded_by,
                a.wording_version_id,
                a.covered_members,
                a.affirmed,
                a.status,
                a.pending_review_type
            FROM gift_aid_declaration_audit a
            WHERE a.id = %s
              AND a.status = 'PENDING_REVIEW'
              AND a.pending_review_type = 'COVERAGE_REQUEST'
              AND NOT EXISTS (
                  SELECT 1
                  FROM gift_aid_declaration_audit newer
                  WHERE newer.supersedes_audit_id = a.id
              )
            FOR UPDATE
            """,
            (
                audit_id,
            ),
        )

        original = cur.fetchone()

        if not original:

            return not_found(
                "Current Gift Aid coverage request not found"
            )

        original_covered_members = (
            original[15]
            or []
        )

        if not isinstance(
            original_covered_members,
            list
        ):

            return bad_request(
                "The coverage request contains invalid covered member data"
            )

        # COVERED_ELSEWHERE currently represents one
        # informal covered member.
        if len(original_covered_members) != 1:

            return bad_request(
                "The coverage request must contain exactly one covered member"
            )

        informal_member = (
            original_covered_members[0]
        )

        if not isinstance(
            informal_member,
            dict
        ):

            return bad_request(
                "The coverage request contains an invalid covered member"
            )

        if informal_member.get(
            "member_id"
        ) is not None:

            return bad_request(
                "The coverage request has already been resolved"
            )

        resolution = resolutions[0]

        if not isinstance(
            resolution,
            dict
        ):

            return bad_request(
                "The resolution must be an object"
            )

        covered_member_index = (
            resolution.get(
                "covered_member_index"
            )
        )

        resolved_member_id = (
            resolution.get(
                "member_id"
            )
        )

        try:

            covered_member_index = int(
                covered_member_index
            )

        except (
            TypeError,
            ValueError
        ):

            return bad_request(
                "Invalid covered_member_index"
            )

        if covered_member_index != 0:

            return bad_request(
                "covered_member_index must be 0"
            )

        try:

            resolved_member_id = int(
                resolved_member_id
            )

        except (
            TypeError,
            ValueError
        ):

            return bad_request(
                "Invalid member_id"
            )

        # The member identified by the admin is the person whose
        # declaration we need to load.
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
                resolved_member_id,
            ),
        )

        resolved_member = (
            cur.fetchone()
        )

        if not resolved_member:

            return bad_request(
                "Resolved member does not exist: "
                + str(resolved_member_id)
            )

        # Load the resolved member's current working declaration.
        #
        # We deliberately look at the latest audit
        # for this member, rather than using the gift_aid_reference
        # stored on the COVERED_ELSEWHERE request.  That request
        # may have a NULL reference or an old cancelled reference.
        cur.execute(
            """
            SELECT
                a.id,
                a.member_id,
                a.gift_aid_reference,
                a.action,
                a.declaration_method,
                a.declaration_text,
                a.declarer_name,
                a.declarer_address_line_1,
                a.declarer_address_line_2,
                a.declarer_postcode,
                a.email_address,
                a.affirmed_date,
                a.invitation_id,
                a.recorded_by,
                a.wording_version_id,
                a.covered_members,
                a.affirmed,
                a.status
            FROM gift_aid_declaration_audit a
                WHERE a.member_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM gift_aid_declaration_audit newer
                      WHERE newer.supersedes_audit_id = a.id
                  )
            ORDER BY a.id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (
                resolved_member_id,
            ),
        )

        working_declaration = (
            cur.fetchone()
        )

        if not working_declaration:

            return bad_request(
                "The resolved member does not have a current confirmed Gift Aid declaration"
            )

        working_action = working_declaration[3]
        working_status = working_declaration[17]

        if working_action in {"CANCELLED", "DECLINED"}:
            return bad_request(
                "The resolved member's current Gift Aid declaration "
                "cannot accept an additional covered member"
            )

        if working_action not in {"AFFIRMED", "UPDATED"}:
            return bad_request(
                "The resolved member does not have a usable current Gift Aid declaration"
            )

        if working_status not in {"CONFIRMED", "PENDING_REVIEW"}:
            return bad_request(
                "The resolved member's current Gift Aid declaration "
                "has an invalid status"
            )

        working_reference = (
            working_declaration[2]
        )

        if working_reference is None:

            return bad_request(
                "The resolved member's current Gift Aid declaration has no Gift Aid reference"
            )

        working_covered_members = (
            working_declaration[15]
            or []
        )

        if not isinstance(
            working_covered_members,
            list
        ):

            return bad_request(
                "The working Gift Aid declaration contains invalid covered member data"
            )

        # The person who raised the COVERED_ELSEWHERE request
        # is the person we may add to the working declaration.
        requester_id = (
            original[1]
        )

        if requester_id is None:

            return bad_request(
                "The coverage request has no requesting member"
            )

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
                requester_id,
            ),
        )

        requester = (
            cur.fetchone()
        )

        if not requester:

            return bad_request(
                "Requesting member does not exist: "
                + str(requester_id)
            )

        # Start with the working declaration's existing
        # covered-member snapshot.
        updated_covered_members = []

        requester_already_present = False

        for covered_member in working_covered_members:

            if not isinstance(
                covered_member,
                dict
            ):

                return bad_request(
                    "The working declaration contains an invalid covered member"
                )

            member_id = covered_member.get(
                "member_id"
            )

            if member_id is not None:

                try:

                    member_id = int(
                        member_id
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return bad_request(
                        "The working declaration contains an invalid member_id"
                    )

                covered_member = dict(
                    covered_member
                )

                covered_member[
                    "member_id"
                ] = member_id

                if member_id == requester_id:

                    requester_already_present = True

            updated_covered_members.append(
                covered_member
            )

        # Add the REQUESTER, not the resolved declaration holder.
        if not requester_already_present:

            updated_covered_members.append(
                {
                    "member_id":
                        requester[0],

                    "membership_number":
                        requester[1],

                    "first_name":
                        requester[2],

                    "surname":
                        requester[3],
                }
            )

        # The new declaration must contain only formal member
        # entries.
        if covered_members_have_informal_entries(
            updated_covered_members
        ):

            return bad_request(
                "The working declaration contains unresolved covered members"
            )

        updated_ids = covered_member_ids(
            updated_covered_members
        )

        # Compare the proposed declaration with the CURRENT
        # Gift Aid relationships for the working declaration's
        # existing reference.
        cur.execute(
            """
            SELECT
                gam.member_id
            FROM gift_aid_members gam
            WHERE gam.gift_aid_reference = %s
              AND (
                  gam.valid_until IS NULL
                  OR gam.valid_until >= CURRENT_DATE
              )
            ORDER BY gam.member_id
            """,
            (
                working_reference,
            ),
        )

        live_rows = cur.fetchall()

        live_ids = {
            int(row[0])
            for row in live_rows
        }

        relationships_match = (
            updated_ids == live_ids
        )

        if relationships_match:

            audit_status = (
                "CONFIRMED"
            )

            pending_review_type = None

        else:

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "RELATIONSHIP_MISMATCH"
            )

        # Create a NEW audit version of the WORKING declaration.
        #
        # The Gift Aid reference belongs to the working declaration
        # and is deliberately retained.
        #
        # The original COVERED_ELSEWHERE audit is NOT its predecessor.
        # The new audit supersedes the working declaration audit.
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
                'UPDATED',
                'MANUAL',
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
                TRUE,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id
            """,
            (
                working_declaration[1],
                working_reference,
                working_declaration[5],
                working_declaration[6],
                working_declaration[7],
                working_declaration[8],
                working_declaration[9],
                working_declaration[10],
                working_declaration[11],
                get_source_ip(event),
                get_user_agent(event),
                working_declaration[12],
                get_cognito_sub(event),
                working_declaration[14],
                audit_status,
                pending_review_type,
                json.dumps(
                    updated_covered_members
                ),
                working_declaration[0],
            ),
        )

        new_audit_id = (
            cur.fetchone()[0]
        )


        # Create a separate audit event recording that the
        # original COVERED_ELSEWHERE request has been resolved.
        #
        # This is NOT a new Gift Aid declaration and therefore
        # does not supersede the coverage request or another
        # declaration audit.
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
                covered_members
            )
            VALUES (
                %s,
                %s,
                'COVERED_ELSEWHERE',
                'MANUAL',
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
                FALSE,
                'CONFIRMED',
                NULL,
                %s
            )
            RETURNING id
            """,
            (
                original[1],
                original[2],
                original[5],
                original[6],
                original[7],
                original[8],
                original[9],
                original[10],
                original[11],
                get_source_ip(event),
                get_user_agent(event),
                original[12],
                get_cognito_sub(event),
                original[14],
                json.dumps(
                    original_covered_members
                ),
            ),
        )

        resolution_audit_id = (
            cur.fetchone()[0]
        )

        # Mark the original COVERED_ELSEWHERE request as resolved.
        cur.execute(
            """
            UPDATE gift_aid_declaration_audit
            SET resolved_by_audit_id = %s
            WHERE id = %s
            """,
            (
                resolution_audit_id,
                original[0],
            ),
        )


        conn.commit()

        return success(
            {
                "audit_id":
                    new_audit_id,

                "supersedes_audit_id":
                    working_declaration[0],

                "source_coverage_request_id":
                    original[0],
                    
                "resolution_audit_id":
                    resolution_audit_id,    

                "gift_aid_reference":
                    working_reference,

                "requesting_member":
                    {
                        "member_id":
                            requester[0],

                        "membership_number":
                            requester[1],

                        "first_name":
                            requester[2],

                        "surname":
                            requester[3],
                    },

                "resolved_declaration_member":
                    {
                        "member_id":
                            resolved_member[0],

                        "membership_number":
                            resolved_member[1],

                        "first_name":
                            resolved_member[2],

                        "surname":
                            resolved_member[3],
                    },

                "action":
                    "UPDATED",

                "method":
                    "MANUAL",

                "affirmed":
                    True,

                "status":
                    audit_status,

                "pending_review_type":
                    pending_review_type,

                "covered_members":
                    updated_covered_members,

                "relationship_ids":
                    sorted(
                        updated_ids
                    ),

                "live_relationship_ids":
                    sorted(
                        live_ids
                    ),

                "relationships_match":
                    relationships_match,
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid resolve coverage error:",
            exc
        )

        return bad_request(
            "Unable to resolve the Gift Aid coverage request"
        )

    finally:

        if conn:
            conn.close()


def handle_resolve_member(
    event,
    audit_id
):

    conn = None

    try:

        try:

            audit_id = int(
                audit_id
            )

        except (
            TypeError,
            ValueError
        ):

            return bad_request(
                "Invalid audit_id"
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

        resolutions = body.get(
            "resolutions"
        )

        if not isinstance(
            resolutions,
            list
        ):

            return bad_request(
                "resolutions must be a list"
            )

        conn = get_connection()

        cur = conn.cursor()

        # Lock the pending audit row while we resolve it.
        cur.execute(
            """
            SELECT
                a.id,
                a.member_id,
                a.gift_aid_reference,
                a.action,
                a.declaration_method,
                a.declaration_text,
                a.declarer_name,
                a.declarer_address_line_1,
                a.declarer_address_line_2,
                a.declarer_postcode,
                a.email_address,
                a.affirmed_date,
                a.invitation_id,
                a.recorded_by,
                a.wording_version_id,
                a.covered_members,
                a.affirmed,
                a.status,
                a.pending_review_type
            FROM gift_aid_declaration_audit a
            WHERE a.id = %s
              AND a.status = 'PENDING_REVIEW'
              AND a.pending_review_type = 'UNRESOLVED_MEMBER'
              AND NOT EXISTS (
                  SELECT 1
                  FROM gift_aid_declaration_audit newer
                  WHERE newer.supersedes_audit_id = a.id
              )
            FOR UPDATE
            """,
            (
                audit_id,
            ),
        )

        original = cur.fetchone()

        if not original:

            return not_found(
                "Current unresolved Gift Aid review not found"
            )

        original_covered_members = (
            original[15]
            or []
        )

        if not isinstance(
            original_covered_members,
            list
        ):

            return bad_request(
                "The pending declaration contains invalid covered member data"
            )

        # Build a lookup of the requested resolutions.
        resolution_map = {}

        for resolution in resolutions:

            if not isinstance(
                resolution,
                dict
            ):

                return bad_request(
                    "Each resolution must be an object"
                )

            covered_member_index = (
                resolution.get(
                    "covered_member_index"
                )
            )

            member_id = (
                resolution.get(
                    "member_id"
                )
            )

            try:

                covered_member_index = int(
                    covered_member_index
                )

            except (
                TypeError,
                ValueError
            ):

                return bad_request(
                    "Invalid covered_member_index"
                )

            try:

                member_id = int(
                    member_id
                )

            except (
                TypeError,
                ValueError
            ):

                return bad_request(
                    "Invalid member_id"
                )

            if covered_member_index in resolution_map:

                return bad_request(
                    "A covered member has been resolved more than once"
                )

            if (
                covered_member_index < 0
                or
                covered_member_index >=
                len(original_covered_members)
            ):

                return bad_request(
                    "covered_member_index is out of range"
                )

            resolution_map[
                covered_member_index
            ] = member_id

        # Every informal entry must be resolved.
        informal_indexes = []

        for index, covered_member in enumerate(
            original_covered_members
        ):

            if not isinstance(
                covered_member,
                dict
            ):

                return bad_request(
                    "The pending declaration contains an invalid covered member"
                )

            if covered_member.get(
                "member_id"
            ) is None:

                informal_indexes.append(
                    index
                )

        for index in informal_indexes:

            if index not in resolution_map:

                return bad_request(
                    "All informal covered members must be resolved before committing"
                )

        # Do not allow a resolution to alter an already formal entry.
        for index in resolution_map:

            covered_member = (
                original_covered_members[
                    index
                ]
            )

            if covered_member.get(
                "member_id"
            ) is not None:

                return bad_request(
                    "A formal covered member does not require resolution"
                )

        # Validate that all selected members actually exist.
        resolved_member_ids = set(
            resolution_map.values()
        )

        for member_id in resolved_member_ids:

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

                return bad_request(
                    "Resolved member does not exist: "
                    + str(member_id)
                )

        # Build the complete corrected covered-member snapshot.
        corrected_covered_members = []

        for index, covered_member in enumerate(
            original_covered_members
        ):

            resolved_member_id = (
                resolution_map.get(
                    index
                )
            )

            if resolved_member_id is not None:

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
                        resolved_member_id,
                    ),
                )

                member_row = cur.fetchone()

                if not member_row:

                    return bad_request(
                        "Resolved member does not exist: "
                        + str(resolved_member_id)
                    )

                corrected_covered_members.append(
                    {
                        "member_id":
                            member_row[0],

                        "membership_number":
                            member_row[1],

                        "first_name":
                            member_row[2],

                        "surname":
                            member_row[3],
                    }
                )

            else:

                corrected_covered_members.append(
                    covered_member
                )

        # Make absolutely sure no informal entries remain.
        if covered_members_have_informal_entries(
            corrected_covered_members
        ):

            return bad_request(
                "The corrected declaration still contains an informal covered member"
            )

        corrected_ids = covered_member_ids(
            corrected_covered_members
        )

        # Get the current live Gift Aid relationships.
        gift_aid_reference = (
            original[2]
        )

        if gift_aid_reference is None:

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
                WHERE gam.gift_aid_reference IS NULL
                  AND (
                      gam.valid_until IS NULL
                      OR gam.valid_until >= CURRENT_DATE
                  )
                ORDER BY gam.member_id
                """
            )

        else:

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

        live_ids = {
            int(row[0])
            for row in live_rows
        }

        relationships_match = (
            corrected_ids == live_ids
        )

        if relationships_match:

            audit_status = (
                "CONFIRMED"
            )

            pending_review_type = None

        else:

            audit_status = (
                "PENDING_REVIEW"
            )

            pending_review_type = (
                "RELATIONSHIP_MISMATCH"
            )

        # Create one new audit row.
        #
        # The original pending row remains untouched.
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
                'UPDATED',
                'MANUAL',
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
                TRUE,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id
            """,
            (
                original[1],
                original[2],
                original[5],
                original[6],
                original[7],
                original[8],
                original[9],
                original[10],
                original[11],
                get_source_ip(event),
                get_user_agent(event),
                original[12],
                get_cognito_sub(event),
                original[14],
                audit_status,
                pending_review_type,
                json.dumps(
                    corrected_covered_members
                ),
                original[0],
            ),
        )

        new_audit_id = (
            cur.fetchone()[0]
        )

        conn.commit()

        return success(
            {
                "audit_id":
                    new_audit_id,

                "supersedes_audit_id":
                    original[0],

                "gift_aid_reference":
                    gift_aid_reference,

                "member_id":
                    original[1],

                "action":
                    "UPDATED",

                "method":
                    "MANUAL",

                "affirmed":
                    True,

                "status":
                    audit_status,

                "pending_review_type":
                    pending_review_type,

                "covered_members":
                    corrected_covered_members,

                "relationship_ids":
                    sorted(
                        corrected_ids
                    ),

                "live_relationship_ids":
                    sorted(
                        live_ids
                    ),

                "relationships_match":
                    relationships_match,
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid resolve member error:",
            exc
        )

        return bad_request(
            "Unable to resolve the Gift Aid covered member"
        )

    finally:

        if conn:
            conn.close()


def handle_confirm_relationships(
    event,
    audit_id
):

    conn = None

    try:

        try:

            audit_id = int(
                audit_id
            )

        except (
            TypeError,
            ValueError
        ):

            return bad_request(
                "Invalid audit_id"
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

        confirmed = body.get(
          "confirmed"
)

        if confirmed is not True:

            return bad_request(
                "Relationship confirmation is required"
            )

        conn = get_connection()

        cur = conn.cursor()

        # Lock the current pending audit row.
        cur.execute(
            """
            SELECT
                a.id,
                a.member_id,
                a.gift_aid_reference,
                a.action,
                a.declaration_method,
                a.declaration_text,
                a.declarer_name,
                a.declarer_address_line_1,
                a.declarer_address_line_2,
                a.declarer_postcode,
                a.email_address,
                a.affirmed_date,
                a.invitation_id,
                a.recorded_by,
                a.wording_version_id,
                a.covered_members,
                a.affirmed,
                a.status,
                a.pending_review_type
            FROM gift_aid_declaration_audit a
            WHERE a.id = %s
              AND a.status = 'PENDING_REVIEW'
              AND a.pending_review_type = 'RELATIONSHIP_MISMATCH'
              AND NOT EXISTS (
                  SELECT 1
                  FROM gift_aid_declaration_audit newer
                  WHERE newer.supersedes_audit_id = a.id
              )
            FOR UPDATE
            """,
            (
                audit_id,
            ),
        )

        original = cur.fetchone()

        if not original:

            return not_found(
                "Current relationship mismatch review not found"
            )

        covered_members = (
            original[15]
            or []
        )

        if not isinstance(
            covered_members,
            list
        ):

            return bad_request(
                "The pending declaration contains invalid covered member data"
            )

        # A relationship mismatch cannot be confirmed while
        # any covered member is still unresolved.
        if covered_members_have_informal_entries(
            covered_members
        ):

            return bad_request(
                "All covered members must be resolved before confirming relationships"
            )

        covered_ids = covered_member_ids(
            covered_members
        )

        # The declaration owner is also a Gift Aid relationship.
        #
        # covered_members contains only people other than the owner.
        owner_id = original[1]

        if owner_id is None:

            return bad_request(
                "The declaration has no declaration owner"
            )

        expected_ids = set(
            covered_ids
        )

        expected_ids.add(
            int(owner_id)
        )

        gift_aid_reference = (
            original[2]
        )

        if gift_aid_reference is None:

            return bad_request(
                "Gift Aid reference is required"
            )

        # Make sure every expected relationship member still exists.
        for member_id in expected_ids:

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

                return bad_request(
                    "Gift Aid relationship member does not exist: "
                    + str(member_id)
                )

        # Get the current live relationships.
        cur.execute(
            """
            SELECT
                member_id
            FROM gift_aid_members
            WHERE gift_aid_reference = %s
              AND (
                  valid_until IS NULL
                  OR valid_until >= CURRENT_DATE
              )
            FOR UPDATE
            """,
            (
                gift_aid_reference,
            ),
        )

        live_rows = cur.fetchall()

        live_ids = {
            int(row[0])
            for row in live_rows
        }

        added_members = sorted(
            expected_ids - live_ids
        )

        removed_members = sorted(
            live_ids - expected_ids
        )

        # The declaration's affirmed date determines the effective
        # date of the relationship changes.
        affirmed_date = original[11]

        # Add relationships which the confirmed declaration says
        # should exist.
        for member_id in added_members:

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
                    member_id,
                    gift_aid_reference,
                ),
            )

        # End relationships which are no longer covered.
        #
        # valid_until is inclusive, so setting it to the
        # declaration date means the old relationship remains
        # valid for that date and is no longer live afterwards.
        for member_id in removed_members:

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
                    affirmed_date,
                    member_id,
                    gift_aid_reference,
                    affirmed_date,
                ),
            )

        # The relationship state should now agree with the
        # declaration.
        cur.execute(
            """
            SELECT
                member_id
            FROM gift_aid_members
            WHERE gift_aid_reference = %s
              AND (
                  valid_until IS NULL
                  OR valid_until >= %s
              )
            ORDER BY member_id
            """,
            (
                gift_aid_reference,
                affirmed_date,
            ),
        )

        final_rows = cur.fetchall()

        final_ids = {
            int(row[0])
            for row in final_rows
        }

        if final_ids != expected_ids:

            return bad_request(
                "Unable to reconcile Gift Aid relationships"
            )

        # Create the confirmed audit version.
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
                'UPDATED',
                'MANUAL',
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
                TRUE,
                'CONFIRMED',
                NULL,
                %s,
                %s
            )
            RETURNING id
            """,
            (
                original[1],
                gift_aid_reference,
                original[5],
                original[6],
                original[7],
                original[8],
                original[9],
                original[10],
                affirmed_date,
                get_source_ip(event),
                get_user_agent(event),
                original[12],
                get_cognito_sub(event),
                original[14],
                json.dumps(
                    covered_members
                ),
                original[0],
            ),
        )

        new_audit_id = (
            cur.fetchone()[0]
        )

        conn.commit()

        return success(
            {
                "audit_id":
                    new_audit_id,

                "supersedes_audit_id":
                    original[0],

                "gift_aid_reference":
                    gift_aid_reference,

                "member_id":
                    original[1],

                "action":
                    "UPDATED",

                "method":
                    "MANUAL",

                "affirmed":
                    True,

                "status":
                    "CONFIRMED",

                "pending_review_type":
                    None,

                "covered_members":
                    covered_members,

                "added_members":
                    added_members,

                "removed_members":
                    removed_members,

                "relationship_ids":
                    sorted(
                        final_ids
                    ),
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid confirm relationships error:",
            exc
        )

        return bad_request(
            "Unable to confirm the Gift Aid relationships"
        )

    finally:

        if conn:
            conn.close()


def handle_dashboard_summary():

    conn = None

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
                WITH current_audits AS (
                    SELECT
                        a.*
                    FROM gift_aid_declaration_audit a
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM gift_aid_declaration_audit newer
                        WHERE newer.supersedes_audit_id = a.id
                    )
                ),
                declaration_counts AS (
                    SELECT
                        COUNT(*) FILTER (
                            WHERE action IN (
                                'AFFIRMED',
                                'UPDATED'
                            )
                            AND status = 'CONFIRMED'
                        ) AS confirmed_declarations,

                        COUNT(*) FILTER (
                            WHERE status = 'PENDING_REVIEW'
                        ) AS pending_review,

                        COUNT(*) FILTER (
                            WHERE action = 'DECLINED'
                              AND status = 'CONFIRMED'
                        ) AS declined,

                        COUNT(*) FILTER (
                            WHERE action = 'CANCELLED'
                              AND status = 'CONFIRMED'
                        ) AS cancelled,

                        COUNT(*) FILTER (
                            WHERE action = 'COVERED_ELSEWHERE'
                              AND status = 'CONFIRMED'
                        ) AS covered_elsewhere

                    FROM current_audits
                ),
                invitation_counts AS (
                    SELECT
                        COUNT(
                            DISTINCT member_id
                        ) AS members_invited,

                        COUNT(*) FILTER (
                            WHERE used_at IS NULL
                              AND expires_at >= CURRENT_TIMESTAMP
                        ) AS open_invitations,

                        COUNT(*) FILTER (
                            WHERE used_at IS NOT NULL
                        ) AS used_invitations

                    FROM gift_aid_invitations
                )
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM members
                    ) AS total_members,

                    confirmed_declarations,
                    pending_review,
                    declined,
                    cancelled,
                    covered_elsewhere,

                    members_invited,
                    open_invitations,
                    used_invitations

                FROM declaration_counts
                CROSS JOIN invitation_counts
                """
            )

            row = cur.fetchone()


            cur.execute(
                """
                SELECT
                    a.id,
                    a.gift_aid_reference,
                    a.member_id,
                    m.membership_number,
                    m.first_name,
                    m.surname,
                    a.action,
                    a.pending_review_type
                FROM gift_aid_declaration_audit a
                JOIN members m
                    ON m.id = a.member_id
                WHERE a.status = 'PENDING_REVIEW'
                  AND a.resolved_by_audit_id IS NULL                
                  AND NOT EXISTS (
                      SELECT 1
                      FROM gift_aid_declaration_audit newer
                      WHERE newer.supersedes_audit_id = a.id
                  )
                ORDER BY a.recorded_at DESC, a.id DESC
                """
)

            pending_rows = cur.fetchall()
            
            
            cur.execute(
                """
                SELECT
                    exception_type,
                    gift_aid_reference,
                    member_id,
                    membership_number,
                    first_name,
                    surname
                FROM gift_aid_relationship_exceptions
                ORDER BY
                    gift_aid_reference,
                    exception_type,
                    member_id
                """
            )

            relationship_exception_rows = cur.fetchall()


        relationship_mismatches = []
        coverage_requests = []
        covered_elsewhere_reviews = []
        unresolved_members = []

        missing_relationships = []
        extra_relationships = []
        inactive_relationships = []
        no_declaration_relationships = []

        for pending_row in pending_rows:

            audit_id = pending_row[0]
            gift_aid_reference = pending_row[1]
            member_id = pending_row[2]
            membership_number = pending_row[3]
            first_name = pending_row[4]
            surname = pending_row[5]
            action = pending_row[6]
            pending_review_type = pending_row[7]

            item = {
                "audit_id": audit_id,
                "gift_aid_reference": gift_aid_reference,
                "member_id": member_id,
                "membership_number": membership_number,
                "first_name": first_name,
                "surname": surname,
                "action": action,
                "pending_review_type": pending_review_type
            }


            if action == "COVERED_ELSEWHERE":

                covered_elsewhere_reviews.append(
                    item
                )

            elif pending_review_type == "RELATIONSHIP_MISMATCH":

                relationship_mismatches.append(
                    item
                )

            elif pending_review_type == "UNRESOLVED_MEMBER":

                unresolved_members.append(
                    item
                )

            elif pending_review_type == "COVERAGE_REQUEST":

                coverage_requests.append(
                    item
                )

        for relationship_row in relationship_exception_rows:

            exception_type = relationship_row[0]

            item = {
                "exception_type": exception_type,
                "gift_aid_reference": relationship_row[1],
                "member_id": relationship_row[2],
                "membership_number": relationship_row[3],
                "first_name": relationship_row[4],
                "surname": relationship_row[5]
            }

            if exception_type == "MISSING_RELATIONSHIP":

                missing_relationships.append(
                    item
                )

            elif exception_type == "EXTRA_RELATIONSHIP":

                extra_relationships.append(
                    item
                )

            elif exception_type == "INACTIVE_DECLARATION_HAS_RELATIONSHIP":

                inactive_relationships.append(
                    item
                )

            elif exception_type == "NO_DECLARATION":

                no_declaration_relationships.append(
                    item
                )


        return success(
            {
                "total_members": row[0],
                "confirmed_declarations": row[1],
                "pending_review": row[2],
                "declined": row[3],
                "cancelled": row[4],
                "covered_elsewhere": row[5],
                "members_invited": row[6],
                "open_invitations": row[7],
                "used_invitations": row[8],

                "relationship_mismatches":
                    relationship_mismatches,
                    
                "unresolved_members": unresolved_members,

                "coverage_requests":
                    coverage_requests,

                "covered_elsewhere_reviews":
                    covered_elsewhere_reviews,

                "missing_relationships":
                    missing_relationships,

                "extra_relationships":
                    extra_relationships,

                "inactive_relationships":
                    inactive_relationships,

                "no_declaration_relationships":
                    no_declaration_relationships
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        return bad_request(
            f"Could not load Gift Aid dashboard summary: {str(exc)}"
        )

    finally:

        if conn:
            conn.close()

def handle_declarations():

    conn = None

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    a.id,
                    a.gift_aid_reference,
                    a.member_id,
                    m.membership_number,
                    m.first_name,
                    m.surname,
                    a.action,
                    a.status,
                    a.declaration_method,
                    a.affirmed_date,
                    a.declarer_name,
                    a.email_address,
                    a.covered_members,
                    a.pending_review_type,
                    a.recorded_at

                FROM gift_aid_declaration_audit a

                JOIN members m
                    ON m.id = a.member_id

                WHERE a.id = (
                    SELECT a2.id
                    FROM gift_aid_declaration_audit a2
                    WHERE a2.gift_aid_reference =
                        a.gift_aid_reference
                    ORDER BY
                        a2.recorded_at DESC,
                        a2.id DESC
                    LIMIT 1
                )

                ORDER BY
                    a.gift_aid_reference
                """
            )

            rows = cur.fetchall()

        declarations = []

        for row in rows:

            declarations.append(
                {
                    "audit_id": row[0],
                    "gift_aid_reference": row[1],
                    "member_id": row[2],
                    "membership_number": row[3],
                    "first_name": row[4],
                    "surname": row[5],
                    "action": row[6],
                    "status": row[7],
                    "declaration_method": row[8],
                    "affirmed_date": (
                        row[9].isoformat()
                        if row[9]
                        else None
                    ),
                    "declarer_name": row[10],
                    "email_address": row[11],
                    "covered_members": row[12],
                    "pending_review_type": row[13],
                    "recorded_at": (
                        row[14].isoformat()
                        if row[14]
                        else None
                    )
                }
            )

        return success(
            {
                "declarations":
                    declarations
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        return bad_request(
            f"Could not load Gift Aid declarations: {str(exc)}"
        )

    finally:

        if conn:
            conn.close()

def handle_admin_get_declaration(event):
    conn = None

    try:
        query = (
            event.get("queryStringParameters")
            or {}
        )

        audit_id = query.get("id")

        if audit_id is None:
            return bad_request(
                "id is required"
            )

        try:
            audit_id = int(audit_id)

        except (TypeError, ValueError):
            return bad_request(
                "Invalid audit_id"
            )

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    a.id,
                    a.member_id,
                    m.membership_number,
                    m.first_name,
                    m.surname,
                    a.gift_aid_reference,
                    a.action,
                    a.declaration_method,
                    a.declaration_text,
                    a.declarer_name,
                    a.declarer_address_line_1,
                    a.declarer_address_line_2,
                    a.declarer_postcode,
                    a.email_address,
                    a.affirmed_date,
                    a.wording_version_id,
                    a.covered_members,
                    a.affirmed,
                    a.status,
                    a.pending_review_type,
                    a.recorded_at
                FROM gift_aid_declaration_audit a
                JOIN members m
                    ON m.id = a.member_id
                WHERE a.id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM gift_aid_declaration_audit newer
                      WHERE newer.supersedes_audit_id = a.id
                  )
                """,
                (audit_id,)
            )

            row = cur.fetchone()

            if row is None:
                return not_found(
                    "Current Gift Aid declaration not found"
                )

            covered_members = row[16] or []

            complete_covered_members = []

            for covered_member in covered_members:

                if covered_member.get("member_id") is None:

                    # Keep unresolved/informal entries unchanged
                    complete_covered_members.append(
                        covered_member
                    )

                    continue

                covered_member_id = int(
                    covered_member["member_id"]
                )

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
                    (covered_member_id,)
                )

                covered_row = cur.fetchone()

                if covered_row is None:

                    # The member no longer exists.
                    # Keep the original entry so the admin
                    # page can still identify the problem.
                    complete_covered_members.append(
                        covered_member
                    )

                    continue

                complete_covered_members.append(
                    {
                        "member_id": covered_row[0],
                        "membership_number": covered_row[1],
                        "first_name": covered_row[2],
                        "surname": covered_row[3],
                    }
                )

        return success(
            {
                "audit_id": row[0],
                "member_id": row[1],
                "membership_number": row[2],
                "first_name": row[3],
                "surname": row[4],
                "gift_aid_reference": row[5],
                "action": row[6],
                "declaration_method": row[7],
                "declaration_text": row[8],
                "declarer_name": row[9],
                "declarer_address_line_1": row[10],
                "declarer_address_line_2": row[11],
                "declarer_postcode": row[12],
                "email_address": row[13],
                "affirmed_date": (
                    row[14].isoformat()
                    if row[14]
                    else None
                ),
                "wording_version_id": row[15],
                "covered_members": complete_covered_members,
                "affirmed": row[17],
                "status": row[18],
                "pending_review_type": row[19],
                "recorded_at": (
                    row[20].isoformat()
                    if row[20]
                    else None
                )
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid admin get declaration error:",
            exc
        )

        return bad_request(
            "Unable to load the Gift Aid declaration"
        )

    finally:

        if conn:
            conn.close()
           
           
def handle_admin_get_declaration_for_member(event):

    conn = None

    try:

        query = (
            event.get("queryStringParameters")
            or {}
        )

        member_id = query.get("id")

        if member_id is None:
            return bad_request(
                "id is required"
            )

        try:
            member_id = int(member_id)

        except (
            TypeError,
            ValueError
        ):
            return bad_request(
                "Invalid member_id"
            )

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    a.id,
                    a.member_id,
                    m.membership_number,
                    m.first_name,
                    m.surname,
                    a.gift_aid_reference,
                    a.action,
                    a.declaration_method,
                    a.declaration_text,
                    a.declarer_name,
                    a.affirmed_date,
                    a.covered_members,
                    a.affirmed,
                    a.status,
                    a.pending_review_type,
                    a.recorded_at
                FROM gift_aid_declaration_audit a
                JOIN members m
                    ON m.id = a.member_id
                WHERE a.member_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM gift_aid_declaration_audit newer
                      WHERE newer.supersedes_audit_id = a.id
                  )
                ORDER BY
                    a.recorded_at DESC,
                    a.id DESC
                LIMIT 1
                """,
                (
                    member_id,
                )
            )

            row = cur.fetchone()

        if row is None:
            return not_found(
                "Member does not have a current Gift Aid declaration"
            )

        action = row[6]
        status = row[13]

        if action in (
            "CANCELLED",
            "DECLINED",
            "COVERED_ELSEWHERE"
        ):
            return not_found(
                "Member does not have a current usable Gift Aid declaration"
            )

        if action not in (
            "AFFIRMED",
            "UPDATED"
        ):
            return not_found(
                "Member does not have a current usable Gift Aid declaration"
            )

        if status not in (
            "CONFIRMED",
            "PENDING_REVIEW"
        ):
            return not_found(
                "Member does not have a current usable Gift Aid declaration"
            )

        return success(
            {
                "audit_id": row[0],
                "member_id": row[1],
                "membership_number": row[2],
                "first_name": row[3],
                "surname": row[4],
                "gift_aid_reference": row[5],
                "action": row[6],
                "declaration_method": row[7],
                "declaration_text": row[8],
                "declarer_name": row[9],
                "affirmed_date": (
                    row[10].isoformat()
                    if row[10]
                    else None
                ),
                "covered_members": (
                    row[11] or []
                ),
                "affirmed": row[12],
                "status": row[13],
                "pending_review_type": row[14],
                "recorded_at": (
                    row[15].isoformat()
                    if row[15]
                    else None
                )
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid declaration-for-member error:",
            exc
        )

        return bad_request(
            "Unable to load the member's Gift Aid declaration"
        )

    finally:

        if conn:
            conn.close()
            
def handle_admin_invitation_check(event):

    conn = None

    try:

        body = json.loads(
            event.get("body") or "{}"
        )

        membership_numbers = body.get(
            "membership_numbers"
        )

        if not isinstance(
            membership_numbers,
            list
        ):
            return bad_request(
                "membership_numbers must be a list"
            )

        if not membership_numbers:
            return bad_request(
                "membership_numbers must not be empty"
            )

        # Clean the supplied membership numbers.
        cleaned_numbers = []

        for value in membership_numbers:

            if value is None:
                continue

            value = str(value).strip()

            if value:
                cleaned_numbers.append(value)

        if not cleaned_numbers:
            return bad_request(
                "No membership numbers were supplied"
            )

        conn = get_connection()

        results = []
        pending_reviews = []
        not_found = []

        with conn.cursor() as cur:

            for membership_number in cleaned_numbers:

                # Find the member.
                cur.execute(
                    """
                    SELECT
                        id,
                        membership_number,
                        first_name,
                        surname
                    FROM members
                    WHERE membership_number = %s
                    """,
                    (
                        membership_number,
                    )
                )

                member = cur.fetchone()

                if member is None:

                    not_found.append(
                        {
                            "membership_number":
                                membership_number
                        }
                    )

                    continue

                member_id = member[0]

                # Find the current Gift Aid declaration.
                cur.execute(
                    """
                    SELECT
                        a.id,
                        a.gift_aid_reference,
                        a.action,
                        a.status,
                        a.pending_review_type
                    FROM gift_aid_declaration_audit a
                    WHERE a.member_id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM gift_aid_declaration_audit newer
                          WHERE newer.supersedes_audit_id = a.id
                      )
                    ORDER BY
                        a.recorded_at DESC,
                        a.id DESC
                    LIMIT 1
                    """,
                    (
                        member_id,
                    )
                )

                declaration = cur.fetchone()

                base_result = {
                    "membership_number":
                        member[1],
                    "member_id":
                        member_id,
                    "first_name":
                        member[2],
                    "surname":
                        member[3]
                }

                if declaration is None:

                    base_result["state"] = (
                        "NO_DECLARATION"
                    )

                    base_result["audit_id"] = None
                    base_result["gift_aid_reference"] = None
                    base_result["action"] = None
                    base_result["status"] = None
                    base_result["pending_review_type"] = None

                    results.append(
                        base_result
                    )

                    continue

                audit_id = declaration[0]
                gift_aid_reference = declaration[1]
                action = declaration[2]
                status = declaration[3]
                pending_review_type = declaration[4]

                base_result["audit_id"] = audit_id
                base_result["gift_aid_reference"] = (
                    gift_aid_reference
                )
                base_result["action"] = action
                base_result["status"] = status
                base_result["pending_review_type"] = (
                    pending_review_type
                )

                # Pending review stops the whole batch.
                if status == "PENDING_REVIEW":

                    base_result["state"] = (
                        "PENDING_REVIEW"
                    )

                    pending_reviews.append(
                        base_result
                    )

                    results.append(
                        base_result
                    )

                    continue

                # A confirmed affirmed/updated declaration.
                if (
                    status == "CONFIRMED"
                    and action in (
                        "AFFIRMED",
                        "UPDATED"
                    )
                ):

                    base_result["state"] = (
                        "EXISTING_DECLARATION"
                    )

                elif action == "CANCELLED":

                    base_result["state"] = (
                        "CANCELLED"
                    )

                elif action == "DECLINED":

                    base_result["state"] = (
                        "DECLINED"
                    )

                elif action == "COVERED_ELSEWHERE":

                    base_result["state"] = (
                        "COVERED_ELSEWHERE"
                    )

                else:

                    base_result["state"] = (
                        "OTHER"
                    )

                results.append(
                    base_result
                )

        # Unknown membership numbers are also an error.
        if not_found:

            return bad_request(
                {
                    "message":
                        "One or more membership numbers were not found",
                    "not_found":
                        not_found,
                    "results":
                        results
                }
            )

        # Pending review blocks the entire batch.
        if pending_reviews:

            return success(
                {
                    "status":
                        "BLOCKED",
                    "message":
                        "Invitation generation is blocked because one or more members have pending Gift Aid reviews.",
                    "pending_reviews":
                        pending_reviews,
                    "results":
                        results
                }
            )

        return success(
            {
                "status":
                    "READY",
                "message":
                    "All members are ready for invitation generation.",
                "results":
                    results
            }
        )

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid invitation check error:",
            exc
        )

        return bad_request(
            "Unable to check members for Gift Aid invitations"
        )

    finally:

        if conn:
            conn.close()
            
            
def handle_admin_invitation_generate(event):
    conn = None

    try:
        body = json.loads(event.get("body") or "{}")

        membership_numbers = body.get("membership_numbers")

        if not isinstance(membership_numbers, list):
            return bad_request("membership_numbers must be a list")

        if not membership_numbers:
            return bad_request("membership_numbers must not be empty")

        # Clean the supplied membership numbers.
        cleaned_numbers = []

        for value in membership_numbers:
            if value is None:
                continue

            value = str(value).strip()

            if value:
                cleaned_numbers.append(value)

        if not cleaned_numbers:
            return bad_request("No membership numbers were supplied")

        # Reject duplicates rather than silently creating multiple
        # invitations for the same member.
        seen = set()
        duplicates = []

        for membership_number in cleaned_numbers:
            if membership_number in seen:
                if membership_number not in duplicates:
                    duplicates.append(membership_number)
            else:
                seen.add(membership_number)

        if duplicates:
            return bad_request({
                "message": "Duplicate membership numbers were supplied",
                "duplicates": duplicates
            })

        conn = get_connection()

        results = []
        pending_reviews = []
        not_found = []

        # ---------------------------------------------------------
        # First phase: check the entire batch before creating
        # anything.
        # ---------------------------------------------------------

        with conn.cursor() as cur:

            for membership_number in cleaned_numbers:

                cur.execute(
                    """
                    SELECT
                        id,
                        membership_number,
                        first_name,
                        surname
                    FROM members
                    WHERE membership_number = %s
                    """,
                    (membership_number,)
                )

                member = cur.fetchone()

                if member is None:
                    not_found.append({
                        "membership_number": membership_number
                    })
                    continue

                member_id = member[0]

                cur.execute(
                    """
                    SELECT
                        a.id,
                        a.gift_aid_reference,
                        a.action,
                        a.status,
                        a.pending_review_type
                    FROM gift_aid_declaration_audit a
                    WHERE a.member_id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM gift_aid_declaration_audit newer
                          WHERE newer.supersedes_audit_id = a.id
                      )
                    ORDER BY
                        a.recorded_at DESC,
                        a.id DESC
                    LIMIT 1
                    """,
                    (member_id,)
                )

                declaration = cur.fetchone()

                result = {
                    "membership_number": member[1],
                    "member_id": member_id,
                    "first_name": member[2],
                    "surname": member[3]
                }

                if declaration is None:
                    result["state"] = "NO_DECLARATION"
                    result["audit_id"] = None
                    result["gift_aid_reference"] = None
                    result["action"] = None
                    result["status"] = None
                    result["pending_review_type"] = None

                    results.append(result)
                    continue

                audit_id = declaration[0]
                gift_aid_reference = declaration[1]
                action = declaration[2]
                status = declaration[3]
                pending_review_type = declaration[4]

                result["audit_id"] = audit_id
                result["gift_aid_reference"] = gift_aid_reference
                result["action"] = action
                result["status"] = status
                result["pending_review_type"] = pending_review_type

                if status == "PENDING_REVIEW":
                    result["state"] = "PENDING_REVIEW"
                    pending_reviews.append(result)
                    results.append(result)
                    continue

                if status == "CONFIRMED" and action in (
                    "AFFIRMED",
                    "UPDATED"
                ):
                    result["state"] = "EXISTING_DECLARATION"

                elif action == "CANCELLED":
                    result["state"] = "CANCELLED"

                elif action == "DECLINED":
                    result["state"] = "DECLINED"

                elif action == "COVERED_ELSEWHERE":
                    result["state"] = "COVERED_ELSEWHERE"

                else:
                    result["state"] = "OTHER"

                results.append(result)

        # ---------------------------------------------------------
        # The whole batch must pass validation before we insert
        # anything.
        # ---------------------------------------------------------

        if not_found:
            conn.rollback()

            return bad_request({
                "message": "One or more membership numbers were not found",
                "not_found": not_found,
                "results": results
            })

        if pending_reviews:
            conn.rollback()

            return success({
                "status": "BLOCKED",
                "message": (
                    "Invitation generation is blocked because one or "
                    "more members have pending Gift Aid reviews."
                ),
                "pending_reviews": pending_reviews,
                "results": results
            })

        # ---------------------------------------------------------
        # All validation has passed.
        #
        # For now we use the same expiry date used during testing.
        # We can make this configurable when we build the admin page.
        # ---------------------------------------------------------

        expires_at = datetime.now(timezone.utc) + timedelta(days=365)

        generated = []

        with conn.cursor() as cur:

            for result in results:

                member_id = result["member_id"]

                # Existing declaration number, or NULL for a member
                # who does not currently have one.
                gift_aid_reference = result["gift_aid_reference"]

                invitation_id = None
                raw_token = None
                stored_expires_at = None

                # -------------------------------------------------
                # Generate a token.
                #
                # The savepoint is important: if PostgreSQL rejects
                # the hash because of the unique constraint, the
                # failed INSERT does not abort the whole transaction.
                # -------------------------------------------------

                for attempt in range(5):

                    raw_token = secrets.token_urlsafe(32)

                    token_hash = hashlib.sha256(
                        raw_token.encode("utf-8")
                    ).hexdigest()

                    savepoint_name = f"token_attempt_{attempt}"

                    cur.execute(
                        f"SAVEPOINT {savepoint_name}"
                    )

                    try:
                        cur.execute(
                            """
                            INSERT INTO gift_aid_invitations (
                                member_id,
                                gift_aid_reference,
                                token_hash,
                                expires_at,
                                used_at
                            )
                            VALUES (
                                %s,
                                %s,
                                %s,
                                %s,
                                NULL
                            )
                            RETURNING
                                id,
                                expires_at
                            """,
                            (
                                member_id,
                                gift_aid_reference,
                                token_hash,
                                expires_at
                            )
                        )

                        invitation_id, stored_expires_at = (
                            cur.fetchone()
                        )

                        cur.execute(
                            f"RELEASE SAVEPOINT {savepoint_name}"
                        )

                        break

                    except psycopg.errors.UniqueViolation as exc:

                        cur.execute(
                            f"ROLLBACK TO SAVEPOINT {savepoint_name}"
                        )

                        error_text = str(exc)

                        if (
                            "gift_aid_invitations_token_hash_key"
                            not in error_text
                        ):
                            raise

                        if attempt == 4:
                            raise RuntimeError(
                                "Unable to generate a unique invitation token "
                                "after 5 attempts"
                            )

                    except Exception:
                        cur.execute(
                            f"ROLLBACK TO SAVEPOINT {savepoint_name}"
                        )
                        raise

                if invitation_id is None:
                    raise RuntimeError(
                        "Invitation could not be created"
                    )

                invitation_url = (
                    "https://admin.suffolkbells.org.uk/"
                    "gift-aid/declaration/"
                    f"?token={raw_token}"
                )

                generated.append({
                    "invitation_id": invitation_id,
                    "member_id": member_id,
                    "membership_number":
                        result["membership_number"],
                    "first_name": result["first_name"],
                    "surname": result["surname"],
                    "state": result["state"],
                    "gift_aid_reference": gift_aid_reference,
                    "expires_at": (
                        stored_expires_at.isoformat()
                        if stored_expires_at
                        else expires_at.isoformat()
                    ),
                    "url": invitation_url
                })

        # ---------------------------------------------------------
        # Everything succeeded.
        # ---------------------------------------------------------

        conn.commit()

        return success({
            "status": "CREATED",
            "message": (
                f"{len(generated)} Gift Aid invitation(s) created."
            ),
            "invitations": generated
        })

    except Exception as exc:

        if conn:
            conn.rollback()

        print(
            "Gift Aid invitation generation error:",
            exc
        )

        return bad_request(
            "Unable to generate Gift Aid invitations"
        )

    finally:

        if conn:
            conn.close()