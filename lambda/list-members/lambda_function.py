from responses import success


def lambda_handler(event, context):

    members = [
        {
            "membership_number": "M001",
            "first_name": "John",
            "surname": "Smith"
        },
        {
            "membership_number": "M002",
            "first_name": "Jane",
            "surname": "Brown"
        },
        {
            "membership_number": "M003",
            "first_name": "David",
            "surname": "Wilson"
        }
    ]

    response = {
        "success": True,
        "count": len(members),
        "members": members
    }

    return success(response)
