import sys
import os

sys.path.insert(0, os.getcwd())

try:
    print("Attempting to import app.main...")
    from app import main
    print("SUCCESS: app.main imported.")
    
    print("Attempting to import app.agent.ai_client...")
    from app.agent import ai_client
    print("SUCCESS: app.agent.ai_client imported.")
    
    print("Attempting to import app.init_db...")
    from app import init_db
    print("SUCCESS: app.init_db imported.")
    
    print("Attempting to import gmail_auth_setup...")
    import gmail_auth_setup
    print("SUCCESS: gmail_auth_setup imported.")
    
    print("\nALL CHECKS PASSED.")
except Exception as e:
    print(f"\nFAILURE: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
