from app import create_app, db
from app.models import User, Category, Item

app = create_app()

def test_app():
    with app.app_context():
        # Setup
        db.create_all()
        
        # Test User Creation
        if not User.query.filter_by(email='test@example.com').first():
            print("Creating test user...")
            u = User(username='testuser', email='test@example.com', password_hash='hash')
            db.session.add(u)
            db.session.commit()
            print("User created.")
        else:
            print("Test user exists.")

        u = User.query.filter_by(email='test@example.com').first()
        
        # Test Category
        print("Creating category...")
        c = Category(name='Books', owner=u)
        db.session.add(c)
        db.session.commit()
        print(f"Category '{c.name}' created.")
        
        # Test Item
        print("Creating item...")
        i = Item(name='The Great Gatsby', category=c)
        db.session.add(i)
        db.session.commit()
        print(f"Item '{i.name}' created.")
        
        # Verify Retrieval
        user_cats = Category.query.filter_by(user_id=u.id).all()
        assert len(user_cats) > 0
        print("Verification Successful: User has categories.")
        
        # Cleanup (Optional)
        # db.session.delete(i)
        # db.session.delete(c)
        # db.session.delete(u)
        # db.session.commit()

if __name__ == '__main__':
    try:
        test_app()
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"TEST FAILED: {e}")
