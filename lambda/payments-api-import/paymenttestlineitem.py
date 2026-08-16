import json
import sys

sys.path.insert(0, "lambda/payments-api-import")

from lambda_function import lambda_handler


event = {
    "requestContext": {
        "http": {
            "method": "POST"
        },
        "authorizer": {
            "jwt": {
                "claims": {
                    "cognito:groups": "PaymentAdmin",
                    "sub": "LOCAL-TEST-USER"
                }
            }
        }
    },
    "routeKey": "POST /payment-import-lines/{id}/items",
    "pathParameters": {
        "id": "1"
    },
    "body": json.dumps({
        "member_id": 1,
        "subscription_amount": 4.00,
        "gift_amount": 0.00,
        "calendar_year": 2026
    })
}


result = lambda_handler(event, None)

print(json.dumps(result, indent=2))
