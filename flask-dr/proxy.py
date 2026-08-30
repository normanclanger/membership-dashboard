import json
import os
import re
import subprocess
import sys

from flask import Flask, request, Response


app = Flask(__name__)

# =========================================================
# Local Hugo CORS
# =========================================================

ALLOWED_ORIGINS = {
    "http://localhost:1313",
    "http://127.0.0.1:1313",
}


@app.after_request
def add_cors_headers(response):

    origin = request.headers.get("Origin")

    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, OPTIONS"
        )
        response.headers["Vary"] = "Origin"

    return response

# =========================================================
# Lambda route definitions
#
# Only READ routes are enabled initially.
# =========================================================

ROUTES = [
    # -----------------------------------------------------
    # member-lookups
    # -----------------------------------------------------
    ("GET", "/api/towers", "member-lookups"),
    ("GET", "/api/membership-classes", "member-lookups"),
    ("GET", "/api/membership-statuses", "member-lookups"),
    ("GET", "/api/full-member-types", "member-lookups"),

    # -----------------------------------------------------
    # membership-api-members
    # -----------------------------------------------------
    ("GET", "/api/members", "membership-api-members"),
    ("GET", "/api/members/{id}", "membership-api-members"),
    (
        "GET",
        "/api/members/{id}/payment-history",
        "membership-api-members",
    ),

    # -----------------------------------------------------
    # payments-api-payments
    # -----------------------------------------------------
    ("GET", "/api/payments", "payments-api-payments"),

    # -----------------------------------------------------
    # payment-reports
    # -----------------------------------------------------
    (
        "GET",
        "/api/reports/payments/summary",
        "payment-reports",
    ),
    (
        "GET",
        "/api/reports/payments/list",
        "payment-reports",
    ),

    # -----------------------------------------------------
    # payments-api-import
    # -----------------------------------------------------
    ("GET", "/api/payment-imports", "payments-api-import"),
    ("GET", "/api/payment-imports/{import_id}", "payments-api-import"),
    (
        "GET",
        "/api/payment-imports/items",
        "payments-api-import",
    ),
    (
        "GET",
        "/api/payment-imports/{import_id}/summary",
        "payments-api-import",
    ),
]


# =========================================================
# Route matching
# =========================================================

def match_route(method, path):
    """
    Return:

        (lambda_directory, route_key, path_parameters)

    or None if there is no matching route.
    """

    for route_method, route_pattern, lambda_dir in ROUTES:

        if method != route_method:
            continue

        pattern_parts = route_pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")

        if len(pattern_parts) != len(path_parts):
            continue

        path_parameters = {}
        matched = True

        for pattern_part, path_part in zip(
            pattern_parts,
            path_parts
        ):
            if (
                pattern_part.startswith("{")
                and pattern_part.endswith("}")
            ):
                parameter_name = pattern_part[1:-1]
                path_parameters[parameter_name] = path_part
            elif pattern_part != path_part:
                matched = False
                break

        if matched:
            return (
                lambda_dir,
                route_pattern,
                path_parameters,
            )

    return None


# =========================================================
# Lambda invocation
# =========================================================

def invoke_lambda(lambda_dir, event):
    """
    Invoke the selected Lambda using the same Python
    interpreter that is running Flask.
    """

    lambda_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "lambda",
            lambda_dir,
        )
    )

    command = [
        sys.executable,
        "-c",
        """
import json
import sys

from lambda_function import lambda_handler

event = json.load(sys.stdin)

result = lambda_handler(event, None)

print(json.dumps(result))
""",
    ]

    result = subprocess.run(
        command,
        cwd=lambda_path,
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    if result.returncode != 0:
        print(
            f"[DR] Lambda failed: {lambda_dir}",
            file=sys.stderr,
        )

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        raise RuntimeError(
            f"Lambda process exited with "
            f"status {result.returncode}"
        )

    # Lambda stdout should contain the JSON response.
    #
    # For now, take the final non-empty line. This allows
    # ordinary diagnostic output to exist above the response.
    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    if not lines:
        raise RuntimeError(
            "Lambda produced no response"
        )

    return json.loads(lines[-1])


# =========================================================
# API proxy
# =========================================================

@app.route(
    "/api/<path:subpath>",
    methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "PUT",
        "OPTIONS",
    ],
)
def api_proxy(subpath):

    method = request.method
    path = "/api/" + subpath

    print(
        f"[DR] Incoming: {method} {path}",
        flush=True,
    )

    # -----------------------------------------------------
    # DR safety rule
    #
    # Only GET is enabled initially.
    # -----------------------------------------------------

    if method == "OPTIONS":
        print(
            f"[DR] CORS preflight: {path}",
            flush=True,
        )
        return Response(status=204)

    if method != "GET":
        print(
            f"[DR] BLOCKED: {method} {path} "
            f"(DR proxy is read-only)",
            flush=True,
        )

        return Response(
            json.dumps({
                "error": "Local disaster-recovery API is read-only"
            }),
            status=403,
            mimetype="application/json",
        )

    matched = match_route(method, path)

    if matched is None:
        print(
            f"[DR] No route: {method} {path}",
            flush=True,
        )

        return Response(
            json.dumps({
                "error": "Unknown local API route"
            }),
            status=404,
            mimetype="application/json",
        )

    lambda_dir, route_pattern, path_parameters = matched

    print(
        f"[DR] Route: {method} {path}",
        flush=True,
    )

    print(
        f"[DR] Lambda: {lambda_dir}",
        flush=True,
    )

    # -----------------------------------------------------
    # Build a Lambda HTTP API-style event.
    # -----------------------------------------------------

    query_parameters = request.args.to_dict()

    event = {
        "requestContext": {
            "http": {
                "method": method,
            },
        },

        "routeKey": f"{method} {route_pattern}",

        "rawPath": path,

        "pathParameters": (
            path_parameters
            if path_parameters
            else None
        ),

        "queryStringParameters": (
            query_parameters
            if query_parameters
            else None
        ),
    }

    print(
        f"[DR] Event: {json.dumps(event)}",
        flush=True,
    )


    try:
        lambda_response = invoke_lambda(
            lambda_dir,
            event,
        )


    except Exception as exc:

        print(
            f"[DR] Lambda error: {exc}",
            file=sys.stderr,
            flush=True,
        )

        return Response(
            json.dumps({
                "error": "Local Lambda execution failed",
                "detail": str(exc),
            }),
            status=500,
            mimetype="application/json",
        )

    # -----------------------------------------------------
    # Pass Lambda response straight through.
    # -----------------------------------------------------

    status_code = lambda_response.get(
        "statusCode",
        500,
    )

    body = lambda_response.get(
        "body",
        "",
    )

    headers = lambda_response.get(
        "headers",
        {},
    )

    print(
        f"[DR] Response: {status_code}",
        flush=True,
    )

    return Response(
        body,
        status=status_code,
        headers=headers,
        mimetype="application/json",
    )


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    print("==============================================")
    print(" Local disaster-recovery API proxy")
    print("==============================================")
    print(f"Python:    {sys.executable}")
    print(f"API_MODE:  {os.environ.get('API_MODE')}")
    print(
        "Database:  "
        + (
            "DATABASE_LOCAL_URL is set"
            if os.environ.get("DATABASE_LOCAL_URL")
            else "DATABASE_LOCAL_URL is NOT set"
        )
    )
    print("Read-only: YES")
    print("Listening: http://127.0.0.1:5000")
    print("==============================================")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )
