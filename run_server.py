import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve

from app import app  # Import your Flask app instance
from core.config import settings # Import your application settings

# Create a Hypercorn Config object
config = Config()
config.application_path = "app:app"  # Path to your Flask app
config.bind = ["127.0.0.1:5000"]
config.accesslog = "-" # Log access to stdout
config.errorlog = "-"   # Log errors to stdout
config.loglevel = "info"

# Set the crucial wsgi_max_body_size
config.wsgi_max_body_size = settings.MAX_TOTAL_UPLOAD_SIZE_BYTES

# Other configurations can be set here if needed, e.g.:
# config.workers = 2

if __name__ == "__main__":
    print(f"Starting Hypercorn server programmatically...")
    print(f"WSGI Max Body Size configured to: {config.wsgi_max_body_size} bytes")
    asyncio.run(serve(app, config)) 