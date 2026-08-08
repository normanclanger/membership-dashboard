from database import get_connection
from responses import success


def lambda_handler(event, context):

    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                membership_number,
                first_name,
                surname
            FROM members;
        """)

        rows = cur.fetchall()

    conn.close()

    members = [
        {
            "membership_number": row[0],
            "first_name": row[1],
            "surname": row[2]
        }
        for row in rows
    ]

    return success({
        "members": members
    })

if __name__ == "__main__":
    print(lambda_handler({}, {}))