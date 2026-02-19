"""
Gmail OAuth2 Setup — Run ONCE to get your refresh token.

Works with BOTH 'Web application' and 'Desktop' OAuth Client types
from Google Cloud Console.
"""
import os
import json
import http.server
import urllib.parse
import webbrowser
import requests

try:
    from dotenv import load_dotenv, set_key
    load_dotenv()
except ImportError:
    pass


def update_env(key, value):
    """Save a value to the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            set_key(env_path, key, value)
            print(f"  ✓ {key} saved to .env")
            return True
        except Exception as e:
            print(f"  ✗ Could not auto-update .env: {e}")
    return False


def run_setup():
    """Run one-time OAuth2 flow to generate a refresh token."""

    client_id = os.environ.get("GMAIL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("ERROR: GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in .env")
        return

    SCOPES = "https://www.googleapis.com/auth/gmail.modify"
    REDIRECT_URI = "http://localhost:8000"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n" + "=" * 50)
    print("  PROCURE-IQ — Gmail API Setup")
    print("=" * 50)
    print(f"\nClient ID: {client_id[:20]}...")
    print(f"Redirect:  {REDIRECT_URI}")
    print(f"\nOpening browser for Google sign-in...")

    # Variable to capture the auth code
    auth_code = [None]

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            if "code" in params:
                auth_code[0] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Success!</h1><p>Gmail authorized. You can close this tab.</p></body></html>")
            elif "error" in params:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                msg = params.get("error", ["unknown"])[0]
                self.wfile.write(f"<html><body><h1>Error</h1><p>{msg}</p></body></html>".encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress server logs

    # Start local server and open browser
    try:
        server = http.server.HTTPServer(("localhost", 8000), CallbackHandler)
    except OSError:
        print("\n✗ Port 8085 is busy. Close other terminals and try again.")
        return

    webbrowser.open(auth_url)
    print("Waiting for authorization...")
    
    # Handle one request (the callback)
    server.handle_request()
    server.server_close()

    if not auth_code[0]:
        print("\n✗ No authorization code received.")
        return

    print("\n✓ Authorization code received!")
    print("  Exchanging for refresh token...")

    # Exchange code for tokens
    token_data = {
        "code": auth_code[0],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    resp = requests.post(TOKEN_URL, data=token_data)
    
    if resp.status_code != 200:
        print(f"\n✗ Token exchange failed: {resp.text}")
        return

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        print(f"\n✗ No refresh token in response. Full response:")
        print(json.dumps(tokens, indent=2))
        return

    # Save to .env
    print(f"\n✓ Refresh token obtained!")
    update_env("GMAIL_REFRESH_TOKEN", refresh_token)

    print(f"\n{'=' * 50}")
    print("  SETUP COMPLETE")
    print(f"{'=' * 50}")
    print("  1. Restart the server: python run.py")
    print("  2. Test connection:    python gmail_checker.py")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    run_setup()
