from database import get_connection
from responses import (
    success,
    bad_request
)


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
        total_amount = 0


        for row in rows:

            subscriptions = row[1] or 0
            gifts = row[2] or 0
            total = row[3] or 0


            districts.append({
                "district_code": row[0],
                "subscriptions": str(
                    subscriptions
                ),
                "gifts": str(
                    gifts
                ),
                "total": str(
                    total
                )
            })


            total_subscriptions += subscriptions
            total_gifts += gifts
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

    if not calendar_year:

        return bad_request({
            "error": "Calendar year is required"
        })


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
        or calendar_year > 2100
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

                WHERE p.calendar_year = %s
            """

            parameters = [
                calendar_year
            ]


            # -------------------------------------------------
            # Optional district filter
            # -------------------------------------------------

            if district:

                sql += """
                    AND d.code = %s
                """

                parameters.append(
                    district
                )


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


    return bad_request({
        "error": "Unsupported request"
    })

