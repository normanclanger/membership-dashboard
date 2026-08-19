import json
import sys

from lambda_function import lambda_handler


# =========================================================
# Helpers
# =========================================================

def make_event(route_key, method, path_parameters=None, body=None):

    return {
        "routeKey": route_key,

        "requestContext": {
            "http": {
                "method": method
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

        "pathParameters": path_parameters or {},

        "body": (
            json.dumps(body)
            if body is not None
            else None
        )
    }


def run_test(title, event):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    result = lambda_handler(event, None)

    print(json.dumps(result, indent=2))

    return result


def get_body(result):

    body = result.get("body")

    if isinstance(body, str):
        return json.loads(body)

    return body


# =========================================================
# STEP 1
# Create £24 allocation on statement line 8
# =========================================================

create_event = make_event(
    route_key="POST /api/payment-import-lines/{id}/items",
    method="POST",
    path_parameters={
        "id": "8"
    },
    body={
        "member_id": 1,
        "subscription_amount": 24,
        "gift_amount": 0,
        "calendar_year": 2026
    }
)

create_result = run_test(
    "STEP 1 - Create £24 allocation on line 8",
    create_event
)


# ---------------------------------------------------------
# Check creation succeeded
# ---------------------------------------------------------

if create_result.get("statusCode") != 201:

    print()
    print("TEST STOPPED")
    print("The allocation could not be created.")

    sys.exit(1)


create_body = get_body(create_result)

item = create_body.get("item")

if not item or not item.get("id"):

    print()
    print("TEST STOPPED")
    print("The allocation was created but no item ID was returned.")

    sys.exit(1)


item_id = item["id"]

print()
print(f"Created payment import item ID: {item_id}")


# =========================================================
# STEP 2
# Change the item from PENDING to READY
# =========================================================

ready_event = make_event(
    route_key="PATCH /api/payment-import-items/{id}",
    method="PATCH",
    path_parameters={
        "id": str(item_id)
    },
    body={
        "status": "READY"
    }
)

ready_result = run_test(
    f"STEP 2 - Mark item {item_id} READY",
    ready_event
)


# ---------------------------------------------------------
# Check READY succeeded
# ---------------------------------------------------------

if ready_result.get("statusCode") != 200:

    print()
    print("TEST STOPPED")
    print("The allocation could not be marked READY.")

    sys.exit(1)


ready_body = get_body(ready_result)

ready_item = ready_body.get("item")

if not ready_item or ready_item.get("status") != "READY":

    print()
    print("TEST STOPPED")
    print("The item was not returned as READY.")

    sys.exit(1)


# =========================================================
# STEP 3
# Commit statement line 8
# =========================================================

commit_event = make_event(
    route_key="POST /api/payment-import-lines/{id}/commit",
    method="POST",
    path_parameters={
        "id": "8"
    }
)

commit_result = run_test(
    "STEP 3 - Commit statement line 8",
    commit_event
)


# ---------------------------------------------------------
# Check commit succeeded
# ---------------------------------------------------------

if commit_result.get("statusCode") != 200:

    print()
    print("TEST FAILED")
    print("Line 8 could not be committed.")

    sys.exit(1)


commit_body = get_body(commit_result)


# =========================================================
# Final result
# =========================================================

print()
print("=" * 70)
print("TEST COMPLETED SUCCESSFULLY")
print("=" * 70)

print()
print("Line:")
print(json.dumps(
    commit_body.get("line"),
    indent=2
))

print()
print("Payments created:")
print(json.dumps(
    commit_body.get("payments_created"),
    indent=2
))

print()
print("Externally resolved items:")
print(json.dumps(
    commit_body.get("externally_resolved_item_ids"),
    indent=2
))