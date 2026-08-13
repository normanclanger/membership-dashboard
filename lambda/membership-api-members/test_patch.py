from lambda_function import lambda_handler


event = {
    "requestContext": {
        "http": {
            "method": "PATCH"
        }
    },

    "pathParameters": {
        "id": "17"
    },

    "queryStringParameters": None,

    "body": """
    {
        "first_name": "Tim",
        "surname": "Hart"
    }
    """
}


result = lambda_handler(event, None)

print("RESULT:")
print(result)
