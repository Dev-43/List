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

def extract_wiki_infobox(soup, category_type='general'):
    """Extracts Director, Year, and Sequel info from Wikipedia Infobox."""
    data = {'director': None, 'year': None, 'sequel_prequel': None}
    
    infobox = soup.find('table', class_='infobox')
    if not infobox:
        return data

    rows = infobox.find_all('tr')
    for row in rows:
        header = row.find('th')
        if not header:
            continue
        header_text = header.get_text(strip=True).lower()
        
        # 1. Director / Author
        if category_type == 'read':
             if any(keyword in header_text for keyword in ['author', 'writer', 'created by']):
                data['director'] = row.find('td').get_text(strip=True) # Storing Author in director column for now
        else:
            if any(keyword in header_text for keyword in ['directed by', 'director', 'created by']):
                data['director'] = row.find('td').get_text(strip=True)

        # 2. Year (Release Date or Publication Date)
        if any(keyword in header_text for keyword in ['release date', 'published', 'publication date']):
             # Extract just the year if possible
             cell_text = row.find('td').get_text(strip=True)
             match = re.search(r'\d{4}', cell_text)
             if match:
                 data['year'] = match.group(0)
        
        # 3. Sequel / Prequel
        if any(keyword in header_text for keyword in ['followed by', 'preceded by', 'next']):
             data['sequel_prequel'] = row.find('td').get_text(strip=True)

    print(f"DEBUG: Extracted Wiki Data: {data}", file=sys.stderr)
    return data

def fetch_meta_data(query, category_type='general', category_name=''):
    query = query.strip()
    original_query = query
    
    # Context logic reinstated per user request
    context_keywords = ""
    cat_name_lower = category_name.lower()
    
    if category_type == 'read':
        if 'manga' in cat_name_lower:
            context_keywords = " manga wikipedia"
        elif 'comic' in cat_name_lower:
             context_keywords = " comic wikipedia"
        else:
            context_keywords = " novel book wikipedia"
            
    elif category_type == 'watch':
        if 'anime' in cat_name_lower:
            context_keywords = " anime wikipedia"
        elif 'series' in cat_name_lower or 'show' in cat_name_lower:
             context_keywords = " tv series wikipedia"
        else:
            context_keywords = " film movie wikipedia"
        
    print(f"DEBUGGING: Query='{query}', Type='{category_type}', List='{category_name}'", file=sys.stderr)
    
    # Only append if not a URL and keywords not already present (basic check)
    if not re.match(r'^https?://', query):
        clean_check = query.lower()
        should_append = True
        
        # Check if context already exists in query to avoid duplication
        # Simple check: if any word from context is in query, skip? 
        # Better: Check specific main keywords
        if category_type == 'read':
             if 'book' in clean_check or 'novel' in clean_check or 'manga' in clean_check or 'comic' in clean_check:
                 should_append = False
        elif category_type == 'watch':
             if 'movie' in clean_check or 'film' in clean_check or 'series' in clean_check or 'anime' in clean_check:
                 should_append = False
                 
        if should_append and context_keywords:
             print(f"DEBUG: Appending context: '{context_keywords}'", file=sys.stderr)
             query = f"{query}{context_keywords}"
        else:
             print(f"DEBUG: Context skipped (already present or none)", file=sys.stderr)
    
    target_url = None
    print(f"DEBUG: Final Processing query: {query}", file=sys.stderr)
    
    # 1. Determine URL
    if not re.match(r'^https?://', original_query):
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
                    # Fallback 3: Wikipedia Guess (Use CLEAN name, not the messy query)
                    wiki_url = f"https://en.wikipedia.org/wiki/{original_query.title().replace(' ', '_')}"
                    wiki_resp = requests.get(wiki_url, headers=ddg_headers, timeout=5)
                    if wiki_resp.status_code == 200:
                        target_url = wiki_url
                        print(f"DEBUG: Guessed Wikipedia URL: {target_url}", file=sys.stderr)
                    else:
                        raise Exception("All search methods failed")

            except Exception as e:
                print(f"DEBUG: Search failed entirely: {e}", file=sys.stderr)
                return {'name': original_query, 'info': '', 'link': '', 'image_url': None, 'director':None, 'year':None, 'sequel_prequel':None}
    
    if not target_url:
        return {'name': original_query, 'info': '', 'link': '', 'image_url': None, 'director':None, 'year':None, 'sequel_prequel':None}
        
    # 2. Scrape Meta
    try:
        print(f"DEBUG: Scrape URL: {target_url}", file=sys.stderr)
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(target_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')

        # 3. Extract Basic Data
        title = soup.title.string if soup.title else original_query
        # Clean Title (Remove " - Wikipedia", " - IMDb", etc.)
        title = re.sub(r' - Wikipedia.*', '', title)
        title = re.sub(r' - IMDb.*', '', title)
        
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc:
            description = meta_desc.get('content', '')
        
        # Image
        image_url = None
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
             image_url = og_image.get('content')
        
        # 4. Extract Rich Data (Wikipedia Specific)
        rich_data = {'director': None, 'year': None, 'sequel_prequel': None}
        if 'wikipedia.org' in target_url:
            rich_data = extract_wiki_infobox(soup, category_type=category_type)
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
        # CRITICAL FIX: Return original_query on error, NOT the modified 'query'
        return {'name': original_query, 'info': '', 'link': target_url, 'image_url': None, 'director':None, 'year':None, 'sequel_prequel':None}


@main.route('/')
def index():
    if current_user.is_authenticated:
        categories = Category.query.filter_by(owner=current_user).all()
        # Ensure default is handled in template or here if empty
        return render_template('dashboard.html', categories=categories)
    return render_template('index.html')

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
        status = 'Pending'
        if category.type == 'watch': status = 'Plan to Watch'
        elif category.type == 'read': status = 'Plan to Read'

        item = Item(
            name=name_input, 
            category_id=category.id,
            status=status
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
        data = fetch_meta_data(item.name, category_type=item.category.type, category_name=item.category.name)
        if data.get('info') or data.get('image_url'):
            item.name = data['name']
            item.image_url = data.get('image_url')
            item.info = data['info']
            item.link = data['link']
            
            # Rich Data
            if data.get('director'): item.director = data['director'][:100]
            if data.get('year'): item.year = data['year'][:20]
            if data.get('sequel_prequel'): item.sequel_prequel = data['sequel_prequel'][:200]
            
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

@main.route('/item/update_status/<int:item_id>', methods=['POST'])
@login_required
def update_item_status(item_id):
    item = Item.query.get_or_404(item_id)
    if item.category.owner != current_user:
        return "Unauthorized", 403
        
    new_status = request.form.get('status')
    if new_status:
        item.status = new_status
        db.session.commit()
        # No flash needed for quick inline update, or maybe a subtle one?
        # flash('Status updated', 'success') 
        
    return redirect(request.referrer or url_for('main.index'))

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
