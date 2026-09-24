from database import get_connection
from responses import (
    success,
    bad_request
)


#**************************************
# Get payment summary for payments dashboard
#**************************************

def get_payment_summary(event):

    query_parameters = (
        event.get("queryStringParameters") or {}
    )

    year = query_parameters.get("year")

    if not year:
        return bad_request({
            "error": "Payment year is required"
        })

    try:
        year = int(year)

    except (TypeError, ValueError):
        return bad_request({
            "error": (
                "Payment year must be a number"
            )
        })

    if year < 1900 or year > 2100:
        return bad_request({
            "error": "Payment year is invalid"
        })

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    d.code AS district_code,

                    COALESCE(
                        SUM(p.subscription_amount),
                        0
                    ) AS subscriptions,

                    COALESCE(
                        SUM(p.gift_amount),
                        0
                    ) AS gifts,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN EXISTS (
                                    SELECT 1
                                    FROM gift_aid_members ga
                                    WHERE ga.member_id = m.id
                                      AND (
                                          ga.valid_until IS NULL
                                          OR p.payment_date <= ga.valid_until
                                      )
                                )
                                THEN p.subscription_amount
                                ELSE 0
                            END
                        ),
                        0
                    ) AS subscriptions_gift_aid_eligible,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN EXISTS (
                                    SELECT 1
                                    FROM gift_aid_members ga
                                    WHERE ga.member_id = m.id
                                      AND (
                                          ga.valid_until IS NULL
                                          OR p.payment_date <= ga.valid_until
                                      )
                                )
                                THEN p.gift_amount
                                ELSE 0
                            END
                        ),
                        0
                    ) AS gifts_gift_aid_eligible,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN EXISTS (
                                    SELECT 1
                                    FROM gift_aid_members ga
                                    WHERE ga.member_id = m.id
                                      AND (
                                          ga.valid_until IS NULL
                                          OR p.payment_date <= ga.valid_until
                                      )
                                )
                                THEN (
                                    p.subscription_amount
                                    + p.gift_amount
                                )
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_gift_aid_eligible,

                    COALESCE(
                        SUM(
                            p.subscription_amount
                            + p.gift_amount
                        ),
                        0
                    ) AS total

                FROM districts d

                LEFT JOIN towers t
                    ON t.district_id = d.id

                LEFT JOIN members m
                    ON m.tower_id = t.id

                LEFT JOIN payments p
                    ON p.member_id = m.id
                    AND EXTRACT(
                        YEAR FROM p.payment_date
                    ) = %s

                GROUP BY
                    d.id,
                    d.code

                ORDER BY
                    d.code;
                """,
                (year,)
            )

            rows = cur.fetchall()


        districts = []

        total_subscriptions = 0
        total_gifts = 0
        total_subscriptions_gift_aid_eligible = 0
        total_gifts_gift_aid_eligible = 0
        total_gift_aid_eligible = 0
        total_amount = 0


        for row in rows:

            subscriptions = row[1] or 0
            gifts = row[2] or 0
            subscriptions_gift_aid_eligible = row[3] or 0
            gifts_gift_aid_eligible = row[4] or 0
            gift_aid_eligible = row[5] or 0
            total = row[6] or 0


            districts.append({
                "district_code": row[0],

                "subscriptions": str(
                    subscriptions
                ),

                "gifts": str(
                    gifts
                ),

                "subscriptions_gift_aid_eligible": str(
                    subscriptions_gift_aid_eligible
                ),

                "gifts_gift_aid_eligible": str(
                    gifts_gift_aid_eligible
                ),

                "total_gift_aid_eligible": str(
                    gift_aid_eligible
                ),

                "total": str(
                    total
                )
            })


            total_subscriptions += subscriptions
            total_gifts += gifts
            total_subscriptions_gift_aid_eligible += (
                subscriptions_gift_aid_eligible
            )
            total_gifts_gift_aid_eligible += (
                gifts_gift_aid_eligible
            )
            total_gift_aid_eligible += (
                gift_aid_eligible
            )
            total_amount += total


        return success({
            "year": year,

            "districts": districts,

            "totals": {

                "subscriptions": str(
                    total_subscriptions
                ),

                "gifts": str(
                    total_gifts
                ),

                "subscriptions_gift_aid_eligible": str(
                    total_subscriptions_gift_aid_eligible
                ),

                "gifts_gift_aid_eligible": str(
                    total_gifts_gift_aid_eligible
                ),

                "total_gift_aid_eligible": str(
                    total_gift_aid_eligible
                ),

                "total": str(
                    total_amount
                )
            }
        })

    finally:

        conn.close()


#**************************************
# Get payment list for year &/or district
#**************************************


def get_payment_list(event):

    query_parameters = (
        event.get("queryStringParameters") or {}
    )

    calendar_year = query_parameters.get(
        "calendar_year"
    )

    district = query_parameters.get(
        "district"
    )


    # ---------------------------------------------------------
    # Validate calendar year
    # ---------------------------------------------------------

    if calendar_year:
        try:

            calendar_year = int(
                calendar_year
            )

        except (TypeError, ValueError):

            return bad_request({
                "error": (
                    "Calendar year must be a number"
                )
            })


        if (
            calendar_year < 1900
            or calendar_year > 2200
        ):

            return bad_request({
                "error": "Calendar year is invalid"
            })


    # ---------------------------------------------------------
    # Normalise optional district
    # ---------------------------------------------------------

    if district:

        district = district.strip().upper()


    # ---------------------------------------------------------
    # Connect to database
    # ---------------------------------------------------------

    conn = get_connection()


    try:

        with conn.cursor() as cur:

            sql = """
                SELECT
                    p.id,
                    p.payment_date,
                    p.statement_reference,

                    m.membership_number,
                    m.first_name,
                    m.surname,

                    t.tower_name,

                    d.code AS district_code,

                    p.subscription_amount,
                    p.gift_amount,
                    p.calendar_year,

                    (
                        p.subscription_amount
                        + p.gift_amount
                    ) AS total

                FROM payments p

                JOIN members m
                    ON m.id = p.member_id

                JOIN towers t
                    ON t.id = m.tower_id

                JOIN districts d
                    ON d.id = t.district_id


            """

            conditions = []
            parameters = []

            if calendar_year:
                conditions.append("p.calendar_year = %s")
                parameters.append(calendar_year)

            if district:
                conditions.append("d.code = %s")
                parameters.append(district)

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)


            # -------------------------------------------------
            # Order by payment date
            # -------------------------------------------------

            sql += """
                ORDER BY
                    p.payment_date,
                    m.surname,
                    m.first_name,
                    p.id;
            """


            cur.execute(
                sql,
                parameters
            )


            rows = cur.fetchall()


        # -----------------------------------------------------
        # Build response
        # -----------------------------------------------------

        payments = []


        for row in rows:

            payments.append({

                "id":
                    row[0],

                "payment_date":
                    row[1].isoformat(),

                "statement_reference":
                    row[2],

                "membership_number":
                    row[3],

                "first_name":
                    row[4],

                "surname":
                    row[5],

                "tower_name":
                    row[6],

                "district_code":
                    row[7],

                "subscription_amount":
                    str(
                        row[8]
                    ),

                "gift_amount":
                    str(
                        row[9]
                    ),

                "calendar_year":
                    row[10],

                "total":
                    str(
                        row[11]
                    )

            })


        return success({

            "calendar_year":
                calendar_year,

            "district":
                district,

            "payments":
                payments

        })


    finally:

        conn.close()


def get_lost_payers(event):

    query_parameters = (
        event.get("queryStringParameters")
        or {}
    )

    calendar_year = query_parameters.get(
        "calendar_year"
    )

    district = query_parameters.get(
        "district"
    )

    # Validate calendar year
    try:
        calendar_year = int(calendar_year)

    except (TypeError, ValueError):
        return bad_request(
            "calendar_year must be a valid year"
        )

    if (
        calendar_year < 1900
        or calendar_year > 2200
    ):
        return bad_request(
            "calendar_year must be between 1900 and 2200"
        )

    previous_year = calendar_year - 1

    # Normalise optional district
    if district:
        district = district.strip().upper()

    sql = """
        SELECT
            m.id,
            m.membership_number,
            m.first_name,
            m.surname,

            mc.code AS membership_class,
            fmt.code AS full_member_type,

            t.tower_name,
            d.code AS district_code

        FROM members m

        JOIN membership_classes mc
            ON mc.id = m.membership_class_id

        LEFT JOIN full_member_types fmt
            ON fmt.id = m.full_member_type_id

        JOIN membership_statuses ms
            ON ms.id = m.membership_status_id

        JOIN towers t
            ON t.id = m.tower_id

        JOIN districts d
            ON d.id = t.district_id

        WHERE
            ms.code = 'ACTIVE'

            AND (
                mc.code = 'ASSOCIATE'

                OR (
                    mc.code = 'FULL'
                    AND (
                        fmt.code <> 'LHM'
                        OR fmt.code IS NULL
                    )
                )
            )

            AND EXISTS (
                SELECT 1
                FROM payments p_previous
                WHERE p_previous.member_id = m.id
                  AND p_previous.calendar_year = %s
            )

            AND NOT EXISTS (
                SELECT 1
                FROM payments p_current
                WHERE p_current.member_id = m.id
                  AND p_current.calendar_year = %s
            )
    """

    parameters = [
        previous_year,
        calendar_year
    ]

    if district:
        sql += """
            AND d.code = %s
        """

        parameters.append(
            district
        )

    sql += """
        ORDER BY
            m.surname,
            m.first_name,
            m.id
    """

    try:

        conn = get_connection()

        try:

            with conn.cursor() as cursor:

                cursor.execute(
                    sql,
                    parameters
                )

                rows = cursor.fetchall()

        finally:

            conn.close()

    except Exception as e:

        print(
            f"Error getting lost payers: {e}"
        )

        return server_error(
            "Unable to retrieve lost payers"
        )

    lost_payers = []

    for row in rows:

        lost_payers.append(
            {
                "id": row[0],
                "membership_number": row[1],
                "first_name": row[2],
                "surname": row[3],
                "membership_class": row[4],
                "full_member_type": row[5],
                "tower_name": row[6],
                "district": row[7]
            }
        )

    return success(
        {
            "calendar_year": calendar_year,
            "previous_year": previous_year,
            "district": district,
            "count": len(lost_payers),
            "members": lost_payers
        }
    )


def lambda_handler(event, context):

    http_method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
    )

    route_key = event.get("routeKey")


    print(
        "DEBUG METHOD:",
        http_method
    )

    print(
        "DEBUG ROUTE KEY:",
        route_key
    )

    # ---------------------------------------------------------
    # Payment report summary 
    # GET /api/reports/payments/summary
    # ---------------------------------------------------------


    if (
        http_method == "GET"
        and route_key
        == "GET /api/reports/payments/summary"
    ):

        return get_payment_summary(event)


    # ---------------------------------------------------------
    # Payment list report
    # GET /api/reports/payments/list
    # ---------------------------------------------------------

    if (
        http_method == "GET"
        and route_key
        == "GET /api/reports/payments/list"
    ):

        return get_payment_list(event)
        
        
    if (
        http_method == "GET"
        and route_key
        == "GET /api/reports/payments/lost-payers"
    ):

        return get_lost_payers(event)


    return bad_request({
        "error": "Unsupported request"
    })

