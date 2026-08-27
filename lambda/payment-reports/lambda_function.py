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


    if (
        http_method == "GET"
        and route_key
        == "GET /api/reports/payments/summary"
    ):

        return get_payment_summary(event)


    return bad_request({
        "error": "Unsupported request"
    })

