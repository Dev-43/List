from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, current_user, logout_user
from app import db
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from requests_oauthlib import OAuth2Session
import secrets
from datetime import datetime, timedelta
from app.auth import auth

# --- Authentication ---

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('auth.register'))
            
        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('main.index'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html')

@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# --- Google OAuth ---
# Note: In production, redirect_uris must be registered in Google Cloud Console matches exactly.
# Locally it's usually http://127.0.0.1:5000/google/callback

def get_google_auth(state=None, token=None):
    if token:
        return OAuth2Session(current_app.config['GOOGLE_CLIENT_ID'], token=token)
    if state:
        return OAuth2Session(current_app.config['GOOGLE_CLIENT_ID'], state=state, redirect_uri=url_for('auth.google_callback', _external=True))
    oauth = OAuth2Session(current_app.config['GOOGLE_CLIENT_ID'], redirect_uri=url_for('auth.google_callback', _external=True))
    return oauth

@auth.route('/login/google')
def login_google():
    google = get_google_auth()
    auth_url, state = google.authorization_url('https://accounts.google.com/o/oauth2/auth', access_type='offline', prompt='select_account')
    # Use session to store state? simpler to just pass for now or use Flask session if needed
    # For simplicity, we trust the callback handling.
    # Ideally store state in session to prevent CSRF.
    from flask import session
    session['oauth_state'] = state
    return redirect(auth_url)

@auth.route('/google/callback')
def google_callback():
    from flask import session
    google = get_google_auth(state=session.get('oauth_state'))
    try:
        token = google.fetch_token('https://accounts.google.com/o/oauth2/token', client_secret=current_app.config['GOOGLE_CLIENT_SECRET'], authorization_response=request.url)
        
        # Get user info
        user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()
        email = user_info['email']
        name = user_info.get('name', email.split('@')[0])
        google_id = user_info['id']
        
        user = User.query.filter_by(email=email).first()
        if not user:
            # Create new user
            # Generate random password for DB constraints if needed, or allow nullable
            user = User(username=name, email=email, oauth_provider='google', oauth_id=google_id)
            db.session.add(user)
            db.session.commit()
        elif not user.oauth_id:
            # Link existing account
            user.oauth_provider = 'google'
            user.oauth_id = google_id
            db.session.commit()
            
        login_user(user)
        return redirect(url_for('main.index'))
    except Exception as e:
        flash(f'Google Login Failed: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))

# --- Password Recovery (Mock) ---
@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            # Generate Token
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Here you would send an email. For now we will flash it or log it.
            # Printing access link to console for demo purposes
            reset_link = url_for('auth.reset_password', token=token, _external=True)
            print(f"RESET LINK: {reset_link}") # Visible in terminal
            flash(f'Password reset link sent to your email (Check console for Dev mode)', 'info')
        else:
             flash('If an account exists, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')

@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Password updated! Please login.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('reset_password.html')
