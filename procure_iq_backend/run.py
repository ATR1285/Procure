import uvicorn
from dotenv import load_dotenv
import os

if __name__ == "__main__":
    load_dotenv()
    # Run FastAPI app on port 5000 to match the current frontend expectations
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
