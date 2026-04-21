import os
import bcrypt
import boto3
from botocore.exceptions import ClientError
from sqlalchemy import text
import streamlit as st
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

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

def verify_google_token(token):
    try:
        # Use the specific Client ID provided by the user in the snippet
        client_id = os.getenv("GOOGLE_CLIENT_ID", "1032401011225-pcjeocvpdigthv15u1qu1hmv8p61cuc0.apps.googleusercontent.com")
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        return idinfo
    except ValueError as e:
        print(f"Token verification error: {e}")
        return None

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
