import os
import sys
import uvicorn

# ⚠️ DEVELOPMENT ONLY: Allow HTTP for OAuth (remove in production with https)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from config import settings

if __name__ == "__main__":
    # Print startup configuration summary
    settings.print_startup_summary()
    
    # Get port from config
    port = settings.PORT
    
    print(f"\n>> Server starting at http://localhost:{port}")
    print(f">> API Documentation: http://localhost:{port}/docs")
    print(f">> API Authentication: {'Enabled' if settings.API_KEY else 'Auto-generating key...'}\n")
    
    # Run FastAPI app with configurable port
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
