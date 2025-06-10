import os
from typing import Tuple, Dict, Any
from sqlalchemy import func
from flask_sqlalchemy.pagination import Pagination
from core.database import db
from core.models import ReportLog, ReportStatus

# Define a dictionary to hold the paths to the prompt files.
# This makes it easier to manage and extend.
PROMPT_FILES: Dict[str, str] = {
    'system_instruction': os.path.join(os.path.dirname(__file__), '..', 'core', 'system_instruction.txt'),
    'style_guide': os.path.join(os.path.dirname(__file__), '..', 'core', 'style_guide.txt'),
    'schema_report': os.path.join(os.path.dirname(__file__), '..', 'core', 'schema_report.txt'),
}

def get_prompt_content(prompt_name: str) -> Tuple[str, bool]:
    """
    Reads the content of a specific prompt file.

    Args:
        prompt_name: The key of the prompt in the PROMPT_FILES dictionary.

    Returns:
        A tuple containing the file content (str) and a boolean indicating success.
    """
    file_path = PROMPT_FILES.get(prompt_name)
    if not file_path or not os.path.exists(file_path):
        return f"Error: Prompt file for '{prompt_name}' not found.", False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read(), True
    except Exception as e:
        print(f"Error reading prompt file '{prompt_name}': {e}")
        return f"Error reading file: {e}", False

def update_prompt_content(prompt_name: str, content: str) -> Tuple[str, bool]:
    """
    Writes new content to a specific prompt file.

    Args:
        prompt_name: The key of the prompt in the PROMPT_FILES dictionary.
        content: The new content to write to the file.

    Returns:
        A tuple containing a status message and a boolean indicating success.
    """
    file_path = PROMPT_FILES.get(prompt_name)
    if not file_path:
        return f"Error: Prompt file for '{prompt_name}' not configured.", False

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        # Capitalize and replace underscores for a user-friendly name in the message
        friendly_name = prompt_name.replace('_', ' ').capitalize()
        return f"{friendly_name} prompt updated successfully.", True
    except Exception as e:
        print(f"Error writing to prompt file '{prompt_name}': {e}")
        return f"Error writing to file: {e}", False

def get_all_prompts() -> Dict[str, str]:
    """
    Reads the content of all configured prompt files.

    Returns:
        A dictionary where keys are prompt names and values are their content.
        If a file cannot be read, the value will be an error message.
    """
    all_prompts = {}
    for name in PROMPT_FILES:
        content, success = get_prompt_content(name)
        all_prompts[name] = content
    return all_prompts

# --- Report Inspector Services ---
def get_paginated_reports(page: int = 1, per_page: int = 20) -> Pagination:
    """
    Fetches a paginated list of all reports from the database,
    ordered by most recent first.
    """
    return db.session.query(ReportLog).order_by(ReportLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

def get_report_by_id(report_id: str) -> ReportLog:
    """
    Fetches a single report and its associated documents by its ID.
    """
    return db.session.query(ReportLog).filter_by(id=report_id).first_or_404()

# --- Dashboard Statistics Services ---

def get_dashboard_stats() -> Dict[str, Any]:
    """
    Fetches statistics for the admin dashboard from the database.
    """
    try:
        reports_generated = db.session.query(ReportLog).filter_by(status=ReportStatus.SUCCESS).count()
        processing_errors = db.session.query(ReportLog).filter_by(status=ReportStatus.ERROR).count()

        # func.sum returns None if there are no rows, so we handle that.
        total_cost_query = db.session.query(func.sum(ReportLog.api_cost_usd)).scalar()
        total_cost = total_cost_query or 0.0

        # func.avg also returns None for no rows.
        avg_gen_time_query = db.session.query(func.avg(ReportLog.generation_time_seconds)).filter_by(status=ReportStatus.SUCCESS).scalar()
        avg_gen_time = avg_gen_time_query or 0

        return {
            "reports_generated": reports_generated,
            "api_cost_monthly_est": f"${total_cost:.2f}",
            "avg_generation_time_secs": f"{avg_gen_time:.0f}s",
            "processing_errors": processing_errors,
        }
    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching dashboard stats: {e}")
        # Return empty/default stats on error
        return {
            "reports_generated": "N/A",
            "api_cost_monthly_est": "$0.00",
            "avg_generation_time_secs": "N/A",
            "processing_errors": "N/A",
        }
