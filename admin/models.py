import os

from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()


class User:
    """
    A simple User model for the admin panel.
    In a real application, this would be backed by a database.
    """

    def __init__(self, username, password, is_active=True):
        self.username = username
        self.password_hash = generate_password_hash(password)
        self.is_active = is_active

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_authenticated(self):
        return True

    def get_id(self):
        return self.username


# For demonstration purposes, we'll create a user from environment variables.
# In a real app, you would load users from a database.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "superadmin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "supersecretpassword")

users = {ADMIN_USERNAME: User(ADMIN_USERNAME, ADMIN_PASSWORD)}
