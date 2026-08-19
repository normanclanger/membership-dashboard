import json

from lambda_function import lambda_handler


event = {
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

    "routeKey": "PATCH /api/payment-import-items/{id}",

    "pathParameters": {
        "id": "10"
    },

    "body": json.dumps({
        "status": "EXCEPTION",
        "exception_reason": "Waiting for membership decision"
    })
}


result = lambda_handler(event, None)

print(json.dumps(result, indent=2))
