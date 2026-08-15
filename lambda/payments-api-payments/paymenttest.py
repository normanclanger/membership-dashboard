import json
import sys

sys.path.insert(0, "lambda/payments-api-payments")

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
    "body": json.dumps({
        "payments": [
            {
                "payment_date": "2026-08-14",
                "statement_reference": "TEST-001",
                "member_id": 1,
                "subscription_amount": 24.00,
                "gift_amount": 0.00,
                "calendar_year": 2026
            }
        ]
    })
}


result = lambda_handler(event, None)

print(json.dumps(result, indent=2))
