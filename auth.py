import os
import bcrypt
import boto3
from botocore.exceptions import ClientError
from sqlalchemy import text
import streamlit as st

# AWS SES Configuration (expected in .env)
SES_REGION = os.getenv("AWS_SES_REGION", "us-east-1")
SENDER_EMAIL = os.getenv("AWS_SES_SENDER")

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def send_verification_email(email, name, code):
    if not SENDER_EMAIL:
        print(f"⚠️ AWS SES SENDER not configured. Verification code for {email}: {code}")
        return False

    client = boto3.client('ses', region_name=SES_REGION)
    try:
        response = client.send_email(
            Destination={'ToAddresses': [email]},
            Message={
                'Body': {
                    'Text': {
                        'Charset': "UTF-8",
                        'Data': f"Hi {name},\n\nWelcome to WerkEsel! Your verification code is: {code}\n\nPlease enter this code in the app to verify your account.",
                    },
                },
                'Subject': {'Charset': "UTF-8", 'Data': "Verify your WerkEsel Account"},
            },
            Source=SENDER_EMAIL,
        )
    except ClientError as e:
        print(f"❌ SES Error: {e.response['Error']['Message']}")
        return False
    return True


def login_user(engine, email, password):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, email, password_hash, name, role, is_verified FROM users WHERE email = :email"), {"email": email}).fetchone()
        if result and result[2] and check_password(password, result[2]):
            return {
                "id": result[0],
                "email": result[1],
                "name": result[3],
                "role": result[4],
                "is_verified": result[5]
            }
    return None

def exchange_google_code(code):
    """Exchanges an authorization code for user info."""
    import requests
    import json
    creds_path = os.getenv("GOOGLE_CREDS_PATH", "client_secret.json")
    if not os.path.exists(creds_path):
        return None

    with open(creds_path, 'r') as f:
        config = json.load(f).get('web')

    data = {
        "code": code,
        "client_id": config['client_id'],
        "client_secret": config['client_secret'],
        "redirect_uri": os.getenv("REDIRECT_URI", "https://tefinitely.com/werkesel/"),
        "grant_type": "authorization_code",
    }

    response = requests.post("https://oauth2.googleapis.com/token", data=data)
    if response.status_code != 200:
        print(f"Token exchange failed: {response.text}")
        return None

    tokens = response.json()
    access_token = tokens.get("access_token")

    # Get User Info using access token
    user_info_res = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if user_info_res.status_code == 200:
        return user_info_res.json()
    return None

def signup_user(engine, email, password, name):
    hashed = hash_password(password)
    import random
    code = str(random.randint(100000, 999999))
    with engine.connect() as conn:
        try:
            conn.execute(
                text("INSERT INTO users (email, password_hash, name, verification_code) VALUES (:email, :password, :name, :code)"),
                {"email": email, "password": hashed, "name": name, "code": code}
            )
            conn.commit()
            send_verification_email(email, name, code)
            return True
        except Exception as e:
            print(f"Signup error: {e}")
            return False

def verify_user_code(engine, email, code):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM users WHERE email = :email AND verification_code = :code"), {"email": email, "code": code}).fetchone()
        if result:
            conn.execute(text("UPDATE users SET is_verified = TRUE, verification_code = NULL WHERE id = :id"), {"id": result[0]})
            conn.commit()
            return True
    return False

def get_or_create_google_user(engine, google_info):
    email = google_info['email']
    google_id = google_info['sub']
    name = google_info.get('name', '')

    with engine.connect() as conn:
        user = conn.execute(text("SELECT id, email, name, role FROM users WHERE google_id = :google_id OR email = :email"), {"google_id": google_id, "email": email}).fetchone()
        if user:
            # Update google_id if it was just an email-based user before
            conn.execute(text("UPDATE users SET google_id = :google_id, is_verified = TRUE WHERE email = :email"), {"google_id": google_id, "email": email})
            conn.commit()
            return {"id": user[0], "email": user[1], "name": user[2], "role": user[3]}
        else:
            res = conn.execute(
                text("INSERT INTO users (email, google_id, name, is_verified) VALUES (:email, :google_id, :name, TRUE)"),
                {"email": email, "google_id": google_id, "name": name}
            )
            conn.commit()
            new_id = res.lastrowid
            return {"id": new_id, "email": email, "name": name, "role": "user"}
