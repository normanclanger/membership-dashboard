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
        "id": "3"
    },
    "body": json.dumps({
        "lines": [
           {
            "statement_reference": "TEST-NEG-001",
            "payment_date": "2026-08-15",
            "statement_amount": 100.00,
            "statement_type": "Counter Credit",
            "description": "Negative allocation test",
            "action": "IMPORT"
        } 
        ]
    })
}


result = lambda_handler(event, None)

print(json.dumps(result, indent=2))
