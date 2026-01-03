import os
import secrets

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
    
    # Database
    # Use SQLite for local development, PostgreSQL (or others) for production
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI') or 'sqlite:///wishlist.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # For HTTPS in production (OAuth requires HTTPS)
    # OAUTHLIB_INSECURE_TRANSPORT should be '1' only for local testing
    OAUTHLIB_INSECURE_TRANSPORT = os.environ.get('OAUTHLIB_INSECURE_TRANSPORT', '0')
