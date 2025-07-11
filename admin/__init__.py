from flask import Blueprint

admin_bp = Blueprint(
    "admin_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/admin/static",
)

from . import routes
