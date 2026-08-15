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


def created(data):
    return response(201, data)


def bad_request(data):
    return response(400, data)


def not_found(data):
    return response(404, data)


def conflict(data):
    return response(409, data)

def forbidden(data):
    return response(403, data)
