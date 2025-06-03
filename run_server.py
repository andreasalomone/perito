import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
import os # Import os

from app import app  # Import your Flask app instance
from core.config import settings # Import your application settings

# Create a Hypercorn Config object
config = Config()
config.application_path = "app:app"  # Path to your Flask app

# Use PORT environment variable provided by Render (default to 5000 for local dev)
# Listen on 0.0.0.0 to be accessible within Render's container
port = int(os.environ.get("PORT", 5000))
config.bind = [f"0.0.0.0:{port}"]

config.accesslog = "-" # Log access to stdout
config.errorlog = "-"   # Log errors to stdout
config.loglevel = settings.LOG_LEVEL.lower() # Use LOG_LEVEL from settings

# Set the crucial wsgi_max_body_size
config.wsgi_max_body_size = settings.MAX_TOTAL_UPLOAD_SIZE_BYTES

# Other configurations can be set here if needed, e.g.:
# config.workers = 2

if __name__ == "__main__":
    print(f"Starting Hypercorn server programmatically on port {port}...")
    print(f"WSGI Max Body Size configured to: {config.wsgi_max_body_size} bytes")
    print(f"Log Level: {config.loglevel}")
    asyncio.run(serve(app, config)) 