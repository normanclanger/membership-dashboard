import boto3

SECRET_NAME = "suffolk-guild/gmail-gift-aid"
REGION = "eu-north-1"

client = boto3.client(
    "secretsmanager",
    region_name=REGION
)

response = client.get_secret_value(
    SecretId=SECRET_NAME
)

secret = response["SecretString"]

print("Secret retrieved successfully.")
print("Secret length:", len(secret))
