from app.routes import fetch_meta_data, app
import sys

# Mocking Google Search to avoid external calls and just test the query construction?
# Actually, the user's issue is likely with the logic construction itself.
# But 'fetch_meta_data' is hard to test without running it because it prints to stderr.
# I will inspect the logic by reading the file again or just TRUSTING the code I wrote and 
# adding explicit logging for the USER to see.

# Wait, I can just ADD MORE LOGGING to the actual route to expose exactly what decision it made.

pass
