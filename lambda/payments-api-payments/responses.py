import json


def response(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(data)
    }


def success(data):
    return response(200, data)


def bad_request(data):
    return response(400, data)


def forbidden(data):
    return response(403, data)
