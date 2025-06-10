from flask_sqlalchemy import SQLAlchemy

# Initialize the SQLAlchemy extension, but don't bind it to the app yet.
# This will be done in the main app factory.
db = SQLAlchemy() 