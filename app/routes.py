from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user, login_required
from app import db
from app.models import User, Category, Item
import sys

# scraping imports
from app.futurescope.metadata import fetch_meta_data

main = Blueprint('main', __name__)

import sys



@main.route('/')
def index():
    if current_user.is_authenticated:
        categories = Category.query.filter_by(owner=current_user).all()
        # Ensure default is handled in template or here if empty
        return render_template('dashboard.html', categories=categories)
    return redirect(url_for('auth.login'))


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
    category = db.session.get(Category, category_id)
    if not category:
        return "Category not found", 404
    if category.owner != current_user:
        return "Unauthorized", 403
    return render_template('list_view.html', category=category)

@main.route('/category/delete/<int:category_id>')
@login_required
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return "Category not found", 404
    if category.owner != current_user:
        return "Unauthorized", 403
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/item/add/<int:category_id>', methods=['POST'])
@login_required
def add_item(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return "Category not found", 404
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
    item = db.session.get(Item, item_id)
    if not item:
        return "Item not found", 404
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
    item = db.session.get(Item, item_id)
    if not item:
        return "Item not found", 404
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
    item = db.session.get(Item, item_id)
    if not item:
        return "Item not found", 404
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
    item = db.session.get(Item, item_id)
    if not item:
        return "Item not found", 404
    if item.category.owner != current_user:
        return "Unauthorized", 403
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/item/toggle/<int:item_id>')
@login_required
def toggle_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return "Item not found", 404
    if item.category.owner != current_user:
        return "Unauthorized", 403
    
    item.status = 'Completed' if item.status != 'Completed' else 'In Wishlist'
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/item/<int:item_id>')
@login_required
def view_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return "Item not found", 404
    if item.category.owner != current_user:
        return "Unauthorized", 403
    return render_template('item_detail.html', item=item)
