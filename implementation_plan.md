# WishList Flask (Python) Upgrade Plan

I will upgrade your existing Python (Flask) web application to be "properly" structured with a real database and user login system.

## User Review Required
> [!NOTE]
> I am switching from the proposed Django plan back to **Flask** (which you were originally using), but organizing it professionally.
> This meets your "keep it in python" request while technically being a web framework.

## Proposed Changes

### Structure
I will organize the project into a standard Python web app structure:
```
WishList/
  run.py               # Entry point
  config.py            # Configuration
  app/
    __init__.py        # App factory
    models.py          # Database Tables (User, Category, Item)
    routes.py          # URL Handling logic
    static/            # CSS/JS (Moved from Frontend)
      style.css
      script.js
    templates/         # HTML (Moved from templates)
      login.html       # [NEW]
      register.html    # [NEW]
      dashboard.html   # [Refined index.html]
```

### Database Models (`app/models.py`)
Using **SQLAlchemy** (standard Python ORM):
- **User**: `id`, `username` (Display Name), `email` (Unique, Used for Login/Recovery), `password_hash`, `oauth_provider`, `oauth_id`
  - *Added support for Password Reset*: `reset_token`, `reset_token_expiry` (`datetime`)
    - **Account Recovery**: "Forgot Password" flow using Email/Gmail.
    - **Smart Search**: Enter a query/URL, and the app fetches details (Title, Image, Description) automatically.
    - **Thumbnails**: Categories and Items now support images/thumbnails for a richer UI.
    - **Item Detail Page**: Clicking an item opens a dedicated page with full details (Image, Description, Link).
2.  **Dashboard**: Shows only the logged-in user's lists.
3.  **Persistence**: Data is saved to `wishlist.db` (SQLite) for local development. For **deployment**, the app will use `SQLALCHEMY_DATABASE_URI` from environment variables to connect to a production database (e.g., PostgreSQL).

### Database Models (`app/models.py`)
- **Category**: `id`, `name`, `user_id`, `image_url` (New)
- **Item**: `id`, `name`, `status`, `date_added`, `info`, `link`, `category_id`, `image_url` (New)

### Frontend Updates & "Nice Things"
-  **Design Overhaul**: Implement a "Premium" glassmorphism look with deep gradients (e.g., Midnight Blue/Purple) and interactions.
-  **Dynamic UX**: Use a single-page-like feel for ensuring smooth transitions between categories.
-  **Flash Messages**: Pop-up notifications for actions (e.g., "Item Added").
-  **Status Toggles**: Visual badges for item status (e.g., "To Watch" vs "Completed").
-  **Base Templates**: Use `base.html` for consistent layout.

### File Structure Migration
I will safely archive the current mixed files into `_legacy` before creating the new clean structure.


## Verification Plan

### Automated Tests
I will create a script `test_app.py` to:
- [ ] Create a user.
- [ ] Log in.
- [ ] Add a list item and verify it saves to the database.

### Manual Verification
1.  Run `python run.py`.
2.  Go to `localhost:5000`.
3.  Register -> Redirect to Dashboard.
4.  Create a Category.
5.  Refresh -> Category remains.
