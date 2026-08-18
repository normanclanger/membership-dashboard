import json
import sys

sys.path.insert(0, "lambda/payments-api-import")

from lambda_function import lambda_handler


event = {
    "routeKey": "PATCH /api/payment-import-lines/{id}",

    "requestContext": {
        "http": {
            "method": "PATCH"
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
        "action": "IMPORT"
    })
    
}


result = lambda_handler(event, None)

print(json.dumps(result, indent=2))
