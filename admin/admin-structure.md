# Admin Panel File Structure

This document outlines the file structure for the admin panel of the AI Report Generator.

```
admin/
├── __init__.py                # Makes the 'admin' directory a Python package
├── admin-structure.md         # This file, documenting the structure
├── models.py                  # Database models specific to the admin panel (e.g., User, PromptVersion)
├── routes.py                  # Flask routes for all admin panel pages (/admin/dashboard, /admin/ai-control, etc.)
├── services.py                # Business logic for the admin panel (e.g., fetching stats, updating prompts)
├── static/
│   ├── css/
│   │   └── admin.css          # Stylesheets for the admin panel
│   └── js/
│       └── admin.js           # JavaScript for interactive admin features (e.g., charts, AJAX calls)
└── templates/
    └── admin/
        ├── base.html          # Base template with common layout (sidebar, navbar)
        ├── dashboard.html     # Template for the main dashboard/mission control page
        ├── ai_control.html    # Template for the AI Control Center (prompt management, model config)
        ├── login.html         # Template for the admin login page
        ├── report_detail.html # Template for the detailed view of a single report
        ├── reports.html       # Template for the table view of all generated reports
        ├── system.html        # Template for system administration (API keys, logs)
        └── templates.html     # Template for managing DOCX templates and static content
```
