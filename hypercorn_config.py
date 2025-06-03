# hypercorn_config.py

# Import the value from your application's settings
from core.config import settings

# Hypercorn configuration settings
# See all options at: https://hypercorn.readthedocs.io/en/latest/how_to_guides/configuring.html#configuration-options

# Bind to address and port
bind = ["127.0.0.1:5000"]

# Set the maximum body size for WSGI requests (in bytes)
# This should match or exceed your Flask application's MAX_TOTAL_UPLOAD_SIZE_BYTES
wsgi_max_body_size = settings.MAX_TOTAL_UPLOAD_SIZE_BYTES

# Set log level (optional, can also be set via CLI)
loglevel = "debug"

# Access log file (optional, can also be set via CLI)
# Using "-" sends it to stdout, which is useful for development
accesslog = "-"

# You can add other Hypercorn settings here if needed, for example:
# workers = 2
# worker_class = "asyncio" # or "uvloop" if uvloop is installed

# Ensure your Flask app is referenced correctly if you were to define 'application_path' here
# application_path = "app:app" # But we'll pass this on the CLI for simplicity for now 