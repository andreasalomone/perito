from flask import render_template, request, redirect, url_for, session, flash
from flask_httpauth import HTTPBasicAuth
from . import admin_bp
from .models import users
from .services import (
    get_all_prompts, 
    update_prompt_content, 
    get_dashboard_stats,
    get_paginated_reports,
    get_report_by_id
)

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    """Verify password for basic auth."""
    user = users.get(username)
    if user and user.check_password(password):
        session['user'] = username
        return username

@admin_bp.route('/admin')
@auth.login_required
def dashboard():
    """Admin dashboard page."""
    stats = get_dashboard_stats()
    return render_template('admin/dashboard.html', user=auth.current_user(), stats=stats)

@admin_bp.route('/admin/login')
def login():
    """Admin login information page."""
    # This page is purely informational. The actual login is handled by the
    # @auth.login_required decorator on protected routes like the dashboard.
    return render_template('admin/login.html')

@admin_bp.route('/admin/logout')
def logout():
    """Admin logout."""
    session.pop('user', None)
    # Returning a 401 response will trigger the browser's auth dialog to clear credentials
    return "You have been logged out.", 401


# Add other admin routes here, all protected by @auth.login_required
@admin_bp.route('/admin/ai-control', methods=['GET', 'POST'])
@auth.login_required
def ai_control():
    if request.method == 'POST':
        # The name of the prompt to update is sent in the form
        prompt_name = request.form.get('prompt_name')
        content = request.form.get('content')
        
        if not prompt_name:
            flash("Invalid request: Missing prompt name.", 'danger')
        else:
            message, success = update_prompt_content(prompt_name, content)
            flash(message, 'success' if success else 'danger')
        
        return redirect(url_for('admin_bp.ai_control'))

    all_prompts = get_all_prompts()
    
    return render_template('admin/ai_control.html', user=auth.current_user(), prompts=all_prompts)

@admin_bp.route('/admin/reports')
@auth.login_required
def reports():
    page = request.args.get('page', 1, type=int)
    pagination = get_paginated_reports(page=page)
    return render_template('admin/reports.html', user=auth.current_user(), pagination=pagination)

@admin_bp.route('/admin/reports/<report_id>')
@auth.login_required
def report_detail(report_id):
    report = get_report_by_id(report_id)
    return render_template('admin/report_detail.html', user=auth.current_user(), report=report)

@admin_bp.route('/admin/templates')
@auth.login_required
def templates():
    return render_template('admin/templates.html', user=auth.current_user())

@admin_bp.route('/admin/system')
@auth.login_required
def system():
    return render_template('admin/system.html', user=auth.current_user())
