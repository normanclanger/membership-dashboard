import json
import sys

sys.path.insert(0, "lambda/payments-api-import")

from lambda_function import lambda_handler


event = {
    "routeKey": "POST /api/payment-import-lines/{id}/commit",

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
        "id": "10"
    },

}

result = lambda_handler(event, None)

print(json.dumps(result, indent=2))

