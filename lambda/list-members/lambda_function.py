from database import get_connection
from responses import success


def lambda_handler(event, context):

    conn = get_connection()
    conn.close()

    return success({
        "success": True,
        "message": "Database connection successful"
    })

