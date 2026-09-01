import os
import psycopg


def get_connection():
    if os.environ.get("API_MODE") == "LOCAL":
        return psycopg.connect(os.environ["DATABASE_LOCAL_URL"])
    return psycopg.connect(os.environ["DATABASE_URL"])
