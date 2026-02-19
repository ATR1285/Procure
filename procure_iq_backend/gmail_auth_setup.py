# Run this ONCE to get your refresh token. Never run again.
import os
import re
from google_auth_oauthlib.flow import InstalledAppFlow

try:
    from dotenv import load_dotenv, set_key
    load_dotenv()
except ImportError:
    pass

def update_env(token):
    """Seamlessly update the .env file with the new refresh token."""
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        try:
            set_key(env_path, "GMAIL_REFRESH_TOKEN", token)
            print(f"SUCCESS: GMAIL_REFRESH_TOKEN has been saved to your .env file automatically.")
            return True
        except Exception as e:
            print(f"WARNING: Could not auto-update .env: {e}")
    else:
        print("WARNING: .env file not found. Please save the token manually.")
    return False

def run_setup():
    """Run one-time OAuth2 flow to generate a refresh token."""
    
    # Scopes required for Gmail access
    SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
    
    # Read credentials from environment variables
    # Explicitly pull from os.environ to ensure load_dotenv() worked
    client_id = os.environ.get("GMAIL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "").strip()
    
    if not client_id or not client_secret:
        print("ERROR: GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in your .env file.")
        return

    # Basic validation: ensure secret doesn't look like a placeholder
    if "your_" in client_id or "your_" in client_secret:
        print("ERROR: It looks like you still have placeholder values in your .env file.")
        return

    # Build credentials dict structure for the flow
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"]
        }
    }

    print("\n" + "="*40)
    print("=== PROCURE-IQ SEAMLESS GMAIL SETUP ===")
    print("="*40)
    print(f"Using Client ID: {client_id[:15]}...")
    print("Opening browser for authentication on port 8085...", flush=True)
    
    try:
        # Initialize the flow
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        
        # Run local server flow on port 8085
        creds = flow.run_local_server(port=8085, prompt='consent', open_browser=True)
        
        print("\n--- AUTHENTICATION SUCCESSFUL ---")
        
        # Automatic update
        updated = update_env(creds.refresh_token)
        
        if not updated:
            print(f"\nYOUR REFRESH TOKEN (Copy this manualy if .env update failed):")
            print(f"{creds.refresh_token}")
        
        print("\nNEXT STEPS:")
        print("1. Your AI Agent will now be able to read project emails.")
        print("2. You can verify the connection by running: python gmail_checker.py")
        print("3. Restart your main server to pick up the changes.")
        
    except Exception as e:
        print(f"\nFAILED to complete authentication: {e}")
        print("\nTROUBLESHOOTING:")
        print("1. Ensure 'Gmail API' is Enabled in Google Cloud Console.")
        print("2. Ensure your email is added to 'Test Users' in OAuth Consent Screen.")
        print("3. Double check that Client ID and Secret in .env are exactly as shown in Google Console.")

if __name__ == "__main__":
    run_setup()
