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
    "pathParameters": {
        "id": "2"
    },
    "body": json.dumps({
        "lines": [
            {
                "statement_reference": "TEST-201",
                "payment_date": "2026-08-15",
                "statement_amount": 100.50,
                "statement_type": "Counter Credit",
                "description": "Test statement £100.50",
                "action": "IMPORT"
            },
            {
                "statement_reference": "TEST-202",
                "payment_date": "2026-08-15",
                "statement_amount": 24.00,
                "statement_type": "Counter Credit",
                "description": "Test statement £24",
                "action": "IMPORT"
            },
            {
                "statement_reference": "TEST-203",
                "payment_date": "2026-08-15",
                "statement_amount": 5.25,
                "statement_type": "Counter Credit",
                "description": "Test ignored statement",
                "action": "IGNORE"
            }
        ]
    })
}


result = lambda_handler(event, None)

print(json.dumps(result, indent=2))