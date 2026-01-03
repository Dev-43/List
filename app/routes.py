from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, current_user, logout_user, login_required
from app import db
from app.models import User, Category, Item
from werkzeug.security import generate_password_hash, check_password_hash
from requests_oauthlib import OAuth2Session
import os
import secrets
from datetime import datetime, timedelta

# scraping imports
import requests
from bs4 import BeautifulSoup
from googlesearch import search
import re

main = Blueprint('main', __name__)

import sys

def extract_wiki_infobox(soup):
    """
    Attempts to extract Director, Year, and Pre/Sequel from Wikipedia Infobox.
    """
    data = {'director': None, 'year': None, 'sequel_prequel': None}
    try:
        infobox = soup.find('table', class_='infobox')
        if not infobox:
            return data
            
        rows = infobox.find_all('tr')
        for row in rows:
            header = row.find('th')
            if not header:
                continue
            header_text = header.get_text().lower()
            cell = row.find('td')
            if not cell:
                continue
            
            # Director
            if 'directed by' in header_text:
                data['director'] = cell.get_text(strip=True)
            
            # Release Date / Year
            if 'release date' in header_text or 'published' in header_text:
                # Try to find a year YYYY
                text = cell.get_text(strip=True)
                year_match = re.search(r'\d{4}', text)
                if year_match:
                    data['year'] = year_match.group(0)
            
            # Sequel / Prequel / Followed by
            if 'followed by' in header_text or 'preceded by' in header_text:
                data['sequel_prequel'] = cell.get_text(strip=True)
                
    except Exception as e:
        print(f"DEBUG: Infobox Parse Error: {e}", file=sys.stderr)
        
    return data

def fetch_meta_data(query):
    """
    Smart Search with Rich Data:
    Returns: {name, info, link, image_url, director, year, sequel_prequel}
    """
    query = query.strip()
    target_url = query
    print(f"DEBUG: Processing query: {query}", file=sys.stderr)
    
    # 1. Determine URL (Same as before)
    if not re.match(r'^https?://', query):
        try:
            print("DEBUG: Searching Google...", file=sys.stderr)
            results = []
            for j in search(query, num_results=1, sleep_interval=1, lang="en"):
                results.append(j)
                break 
            
            if results:
                target_url = results[0]
                print(f"DEBUG: Found URL via Google: {target_url}", file=sys.stderr)
            else:
                raise Exception("No Google results")

        except Exception as e:
            print(f"DEBUG: Google Search failed ({e}). Trying DuckDuckGo...", file=sys.stderr)
            try:
                # Fallback: Scrape DuckDuckGo HTML
                ddg_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                ddg_resp = requests.get('https://html.duckduckgo.com/html/', params={'q': query}, headers=ddg_headers, timeout=10)
                ddg_soup = BeautifulSoup(ddg_resp.content, 'html.parser')
                first_link = ddg_soup.find('a', class_='result__a')
                if first_link:
                    target_url = first_link['href']
                    print(f"DEBUG: Found URL via DuckDuckGo: {target_url}", file=sys.stderr)
                else:
                    print(f"DEBUG: DDG parsing failed (Len: {len(ddg_resp.content)}). Trying Wikipedia...", file=sys.stderr)
                    # Fallback 3: Wikipedia Guess
                    wiki_url = f"https://en.wikipedia.org/wiki/{query.title().replace(' ', '_')}"
                    wiki_resp = requests.get(wiki_url, headers=ddg_headers, timeout=5)
                    if wiki_resp.status_code == 200:
                         target_url = wiki_url
                         print(f"DEBUG: Found URL via Wikipedia Fallback: {target_url}", file=sys.stderr)
                    else:
                         return {'name': query, 'info': 'No results found', 'link': None, 'image_url': None}
            except Exception as ddg_e:
                print(f"DEBUG: All Search methods failed: {ddg_e}", file=sys.stderr)
                return {'name': query, 'info': 'Search failed', 'link': None, 'image_url': None}

    # 2. Fetch URL
    try:
        print(f"DEBUG: Fetching {target_url}...", file=sys.stderr)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
             # ... other headers
        }
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 3. Extract Data (Existing)
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else soup.title.string if soup.title else query
        
        og_desc = soup.find("meta", property="og:description")
        if not og_desc:
            og_desc = soup.find("meta", attrs={"name": "description"})
        description = og_desc["content"] if og_desc else ""
        
        og_image = soup.find("meta", property="og:image")
        image_url = og_image["content"] if og_image else None
        
        if not image_url:
            images = soup.find_all('img')
            for img in images:
                src = img.get('src')
                if src and src.startswith('http') and 'logo' not in src.lower() and 'icon' not in src.lower():
                     image_url = src
                     break
        
        # 4. Extract Rich Data (Wikipedia Specific)
        rich_data = {'director': None, 'year': None, 'sequel_prequel': None}
        if 'wikipedia.org' in target_url:
            rich_data = extract_wiki_infobox(soup)
            print(f"DEBUG: Extracted Wiki Data: {rich_data}", file=sys.stderr)

        print(f"DEBUG: Scraped - Title: {title}, Image: {bool(image_url)}", file=sys.stderr)

        return {
            'name': str(title).strip()[:100], 
            'info': str(description).strip()[:500], 
            'link': target_url,
            'image_url': image_url,
            'director': rich_data['director'],
            'year': rich_data['year'],
            'sequel_prequel': rich_data['sequel_prequel']
        }
    except Exception as e:
        print(f"DEBUG: Fetch/Parse Error: {e}", file=sys.stderr)
        return {'name': query, 'info': '', 'link': target_url, 'image_url': None, 'director':None, 'year':None, 'sequel_prequel':None}


@main.route('/')
@login_required
def index():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', categories=categories)

# --- Authentication ---

@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('main.register'))
            
        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
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

@main.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.login'))

# --- Google OAuth ---
# Note: In production, redirect_uris must be registered in Google Cloud Console matches exactly.
# Locally it's usually http://127.0.0.1:5000/google/callback

def get_google_auth(state=None, token=None):
    if token:
        return OAuth2Session(current_app.config['GOOGLE_CLIENT_ID'], token=token)
    if state:
        return OAuth2Session(current_app.config['GOOGLE_CLIENT_ID'], state=state, redirect_uri=url_for('main.google_callback', _external=True))
    oauth = OAuth2Session(current_app.config['GOOGLE_CLIENT_ID'], redirect_uri=url_for('main.google_callback', _external=True))
    return oauth

@main.route('/login/google')
def login_google():
    google = get_google_auth()
    auth_url, state = google.authorization_url('https://accounts.google.com/o/oauth2/auth', access_type='offline', prompt='select_account')
    # Use session to store state? simpler to just pass for now or use Flask session if needed
    # For simplicity, we trust the callback handling.
    # Ideally store state in session to prevent CSRF.
    from flask import session
    session['oauth_state'] = state
    return redirect(auth_url)

@main.route('/google/callback')
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
        return redirect(url_for('main.login'))

# --- Password Recovery (Mock) ---
@main.route('/forgot_password', methods=['GET', 'POST'])
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
            reset_link = url_for('main.reset_password', token=token, _external=True)
            print(f"RESET LINK: {reset_link}") # Visible in terminal
            flash(f'Password reset link sent to your email (Check console for Dev mode)', 'info')
        else:
             flash('If an account exists, a reset link has been sent.', 'info')
        return redirect(url_for('main.login'))
    return render_template('forgot_password.html')

@main.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('main.login'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Password updated! Please login.', 'success')
        return redirect(url_for('main.login'))
        
    return render_template('reset_password.html')


# --- Categories & Items ---

@main.route('/category/add', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name')
    cat_type = request.form.get('type', 'general')
    if name:
        category = Category(name=name, type=cat_type, owner=current_user)
        db.session.add(category)
        db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/list/<int:category_id>')
@login_required
def view_list(category_id):
    category = Category.query.get_or_404(category_id)
    if category.owner != current_user:
        return "Unauthorized", 403
    return render_template('list_view.html', category=category)

@main.route('/category/delete/<int:category_id>')
@login_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.owner != current_user:
        return "Unauthorized", 403
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/item/add/<int:category_id>', methods=['POST'])
@login_required
def add_item(category_id):
    category = Category.query.get_or_404(category_id)
    if category.owner != current_user:
        return "Unauthorized", 403
        
    name_input = request.form.get('name')

    if name_input:
        # Simple Fast Add
        item = Item(
            name=name_input, 
            category_id=category.id,
            status='Future Read/Watch'
        )
        db.session.add(item)
        db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/item/enhance/<int:item_id>')
@login_required
def enhance_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.category.owner != current_user:
        return "Unauthorized", 403
    
    # Smart Search Logic
    try:
        meta = fetch_meta_data(item.name)
        if meta.get('image_url') or meta.get('info'):
            item.image_url = meta.get('image_url')
            item.info = meta.get('info')
            item.link = meta.get('link')
            
            # Rich Data
            if meta.get('director'): item.director = meta['director'][:100]
            if meta.get('year'): item.year = meta['year'][:20]
            if meta.get('sequel_prequel'): item.sequel_prequel = meta['sequel_prequel'][:200]
            
            db.session.commit()
            flash(f"Magic performed on: {item.name}", 'success')
        else:
             flash(f"Could not find details for {item.name}", 'warning')
    except Exception as e:
        flash(f"Enhancement failed: {str(e)}", 'danger')

    return redirect(request.referrer or url_for('main.index'))

@main.route('/item/update_details/<int:item_id>', methods=['POST'])
@login_required
def update_item_details(item_id):
    item = Item.query.get_or_404(item_id)
    if item.category.owner != current_user:
        return "Unauthorized", 403
        
    # Manual Update
    item.info = request.form.get('info')
    item.link = request.form.get('link')
    item.status = request.form.get('status')
    
    db.session.commit()
    flash('Details updated successfully!', 'success')
    return redirect(url_for('main.view_item', item_id=item.id))

@main.route('/item/delete/<int:item_id>')
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.category.owner != current_user:
        return "Unauthorized", 403
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/item/toggle/<int:item_id>')
@login_required
def toggle_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.category.owner != current_user:
        return "Unauthorized", 403
    
    item.status = 'Completed' if item.status != 'Completed' else 'In Wishlist'
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/item/<int:item_id>')
@login_required
def view_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.category.owner != current_user:
        return "Unauthorized", 403
    return render_template('item_detail.html', item=item)
