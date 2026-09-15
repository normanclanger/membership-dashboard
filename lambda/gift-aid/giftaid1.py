from responses import (
    success,
    bad_request,
    not_found,
    forbidden,
    created,
)

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

        conn.commit()

        return success(
            {
                "audit_id":
                    new_audit_id,

                "supersedes_audit_id":
                    working_declaration[0],

                "source_coverage_request_id":
                    original[0],

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

