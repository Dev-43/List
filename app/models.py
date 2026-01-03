from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    # OAuth
    oauth_provider = db.Column(db.String(20)) # e.g. 'google'
    oauth_id = db.Column(db.String(100)) # Unique ID from provider
    
    # Password Reset
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    
    # Relations
    categories = db.relationship('Category', backref='owner', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(500)) # New: Thumbnail
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.relationship('Item', backref='category', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Category('{self.name}')"

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='In Wishlist') # In Wishlist, Purchased, etc.
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    info = db.Column(db.Text)
    link = db.Column(db.String(500)) # Increased length for long URLs
    image_url = db.Column(db.String(500)) # New: Cover Image
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

    def __repr__(self):
        return f"Item('{self.name}', '{self.status}')"
