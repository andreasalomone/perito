from flask import Flask, render_template, request, send_file, Response as FlaskResponse, flash, redirect, url_for, g
import os
import logging
import tempfile
import shutil
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import document_processor
import llm_handler
import docx_generator
from datetime import datetime
from typing import List, Tuple, Union, Dict, Any, Optional
import io
import uuid
from flask import get_flashed_messages
import asyncio
import sys

from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

from core.config import settings

load_dotenv()

app = Flask(__name__)
auth = HTTPBasicAuth()

# Define users in environment variables for security
# In Render, set BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD
users = {
    os.environ.get("BASIC_AUTH_USERNAME", "admin"): generate_password_hash(os.environ.get("BASIC_AUTH_PASSWORD", "defaultpassword"))
}

@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username
    return None

# --- Logging Configuration ---
# Main application logging format that includes request_id
main_log_format = '%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s'
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                    format=main_log_format) # Apply main format globally first

# Specific logger for startup messages, potentially before request_id is meaningful or filter is fully active
logger_for_startup = logging.getLogger("hypercorn_startup_test")
# If this logger only logs at startup, it might not need/have request_id.
# To avoid errors, give it a simple handler and formatter if it logs before the filter is guaranteed.
if not logger_for_startup.handlers: # Add a specific handler if none exist (e.g. in some environments)
    startup_handler = logging.StreamHandler(sys.stderr) # Log to stderr
    startup_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s') # No request_id
    startup_handler.setFormatter(startup_formatter)
    logger_for_startup.addHandler(startup_handler)
    logger_for_startup.propagate = False # Don't pass to root if we have a specific handler

logger_for_startup.info("Flask application starting up / reloaded by Hypercorn (via dedicated startup logger).")

# Configure httpx logger to be less verbose
logging.getLogger("httpx").setLevel(logging.WARNING)

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        # Print directly to stderr to avoid recursion and bypass logging system for this debug
        # print(f"RequestIdFilter: ENTERED. Filtering record for logger '{record.name}'. Message: '{record.getMessage()[:70]}...'", file=sys.stderr)
        
        effective_request_id = 'N/A_FILTER_DEFAULT_INIT' 
        try:
            # g is imported at module level 'from flask import g'
            # Accessing g.get() outside of app/request context should raise RuntimeError
            # print(f"RequestIdFilter: DEBUG Attempting g.get for '{record.name}'", file=sys.stderr)
            effective_request_id = g.get('request_id', 'N/A_FROM_G_GET_WITH_DEFAULT')
            # print(f"RequestIdFilter: DEBUG g.get succeeded for '{record.name}', effective_request_id: {effective_request_id}", file=sys.stderr)
        except RuntimeError:
            effective_request_id = 'N/A_RUNTIME_ERROR'
            # print(f"RequestIdFilter: DEBUG RuntimeError for '{record.name}'", file=sys.stderr)
        except NameError:
            # This should ideally not happen if 'from flask import g' at module level is successful
            effective_request_id = 'N/A_NAME_ERROR_G_NOT_FOUND'
            # print(f"RequestIdFilter: DEBUG NameError for '{record.name}'", file=sys.stderr)
        except Exception as e:
            # Catch any other unexpected exception during g.get() or related operations
            effective_request_id = f'N/A_UNEXPECTED_FILTER_ERR_{type(e).__name__}'
            # print(f"RequestIdFilter: DEBUG Unexpected Exception '{type(e).__name__}' for '{record.name}': {e}", file=sys.stderr)
        
        record.request_id = effective_request_id
        # print(f"RequestIdFilter: FINISHED. Set record.request_id to '{record.request_id}' for logger '{record.name}'", file=sys.stderr)
        return True

logger = logging.getLogger(__name__)

# Apply the filter to all handlers of the root logger
# This ensures that any logger (including Werkzeug's, if it uses the root handlers)
# will have its records passed through this filter before formatting.
_request_id_filter_instance = RequestIdFilter()
for handler in logging.root.handlers:
    handler.addFilter(_request_id_filter_instance)

# If the app-specific logger has its own handlers (not just propagating to root),
# and those handlers also use a format string with request_id,
# then uncommenting the line below for the app_logger might be necessary.
# However, typically basicConfig configures root, and app loggers propagate to root.
# logger.addFilter(_request_id_filter_instance) # Redundant if app logger propagates and root handlers have the filter.

# --- End Logging Configuration ---

app.config['SECRET_KEY'] = settings.FLASK_SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = settings.MAX_TOTAL_UPLOAD_SIZE_BYTES

def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_EXTENSIONS

@app.before_request
def before_request_func():
    g.request_id = str(uuid.uuid4())
    logger.debug(f"Assigned request ID: {g.request_id} for {request.path}")

@app.before_request
@auth.login_required
def protect_all_routes():
    if request.endpoint and request.endpoint.startswith('static'):
        return # Don't protect static files
    pass # Let auth.login_required handle it

@app.route('/')
def index() -> str:
    logger.info(f"Accessing index route /. Request ID: {g.get('request_id', 'N/A_index')}")
    return render_template('index.html')

# Helper Functions for upload_files
def _validate_file_list(files: List[FileStorage]) -> Optional[Tuple[str, str]]:
    """Validates the list of files to be uploaded."""
    if not files or all(f.filename == '' for f in files):
        logger.info("No files selected for uploading.")
        return "No files selected for uploading.", "warning"
    return None

def _add_text_data_to_processed_list(
    processed_file_data_list: List[Dict[str, Any]], 
    current_total_length: int, 
    text_content: str, 
    filename: str, 
    source_description: str
) -> Tuple[List[Dict[str, Any]], int, Optional[Tuple[str, str]]]:
    """Helper to add extracted text to the list, handling truncation and size limits."""
    flash_message = None
    available_chars = settings.MAX_EXTRACTED_TEXT_LENGTH - current_total_length
    if available_chars <= 0:
        logger.warning(
            f"Maximum total extracted text length reached before processing content from {filename} ({source_description}). Skipping."
        )
        flash_message = (
            f"Skipped some content from {filename} ({source_description}) as maximum total text limit was reached.",
            "warning",
        )
        return processed_file_data_list, current_total_length, flash_message

    if len(text_content) > available_chars:
        text_content = text_content[:available_chars]
        logger.warning(
            f"Truncated text from {filename} ({source_description}) to fit within MAX_EXTRACTED_TEXT_LENGTH."
        )
        flash_message = (
            f"Content from {filename} ({source_description}) was truncated to fit the overall text limit.",
            "warning",
        )

    processed_file_data_list.append(
        {
            "type": "text",
            "filename": filename,
            "content": text_content,
            "source": source_description,
        }
    )
    current_total_length += len(text_content)
    return processed_file_data_list, current_total_length, flash_message

async def _process_single_file_storage(
    file_storage: FileStorage,
    temp_dir: str,
    current_total_extracted_text_length: int
) -> Tuple[List[Dict[str, Any]], int, List[Tuple[str, str]], Optional[str]]:
    """Processes a single FileStorage object, returning processed data, new text length, flash messages, and filename."""
    # Ensure g.request_id is available here if needed for deep logging
    # logger.debug(f"Processing single file. Request ID: {g.get('request_id', 'N/A_process_single')}")
    processed_entries: List[Dict[str, Any]] = []
    text_length_added_by_this_file = 0
    flash_messages: List[Tuple[str, str]] = []
    successfully_saved_filename: Optional[str] = None

    original_filename_for_logging = file_storage.filename or "<unknown>"

    # Individual file size check (re-check, as total size is checked before loop)
    # file_storage.seek(0, os.SEEK_END)
    # current_file_size = file_storage.tell()
    # file_storage.seek(0)
    # Note: The guide suggested checking file size here. However, the original code already has a robust check
    # for individual file size *before* this helper would be called (inside the main loop).
    # To avoid redundancy and keep this helper focused, we'll assume individual size check is done by the caller.
    # If not, it should be added here or, preferably, ensured by the caller.

    if not allowed_file(original_filename_for_logging):
        logger.warning(f"File type not allowed: {original_filename_for_logging}, skipping.")
        flash_messages.append((f"File type not allowed for {original_filename_for_logging}. It has been skipped.", "warning"))
        processed_entries.append({'type': 'unsupported', 'filename': original_filename_for_logging, 'message': 'File type not allowed'})
        return processed_entries, text_length_added_by_this_file, flash_messages, successfully_saved_filename

    filename = secure_filename(original_filename_for_logging)
    if not filename:
        logger.warning(f"secure_filename resulted in empty filename for original: {original_filename_for_logging}, skipping.")
        flash_messages.append(("A file with an invalid name was skipped after securing.", "warning"))
        processed_entries.append({'type': 'error', 'filename': original_filename_for_logging, 'message': 'Invalid filename after securing.'})
        return processed_entries, text_length_added_by_this_file, flash_messages, successfully_saved_filename

    filepath = os.path.join(temp_dir, filename)

    try:
        await asyncio.to_thread(file_storage.save, filepath)
        logger.info(f"Saved uploaded file to temporary path: {filepath}")
        successfully_saved_filename = filename # Mark as saved for display list

        processed_info: Dict[str, Any] = await asyncio.to_thread(
            document_processor.process_uploaded_file, filepath, temp_dir
        )

        temp_processed_file_data_list_for_this_file: List[Dict[str, Any]] = []
        current_length_for_this_file_processing = current_total_extracted_text_length

        if processed_info.get('type') == 'error' or processed_info.get('type') == 'unsupported':
            processed_entries.append(processed_info)
        elif processed_info.get('original_filetype') == 'eml':
            if processed_info.get('type') == 'text' and processed_info.get('content'):
                temp_processed_file_data_list_for_this_file, current_length_for_this_file_processing, flash_msg = \
                    _add_text_data_to_processed_list(
                        temp_processed_file_data_list_for_this_file, 
                        current_length_for_this_file_processing, 
                        processed_info['content'], 
                        filename, 
                        "email body"
                    )
                if flash_msg: flash_messages.append(flash_msg)
            
            if 'processed_attachments' in processed_info and isinstance(processed_info['processed_attachments'], list):
                for attachment_data in processed_info['processed_attachments']:
                    if attachment_data.get('type') == 'text' and attachment_data.get('content'):
                        temp_processed_file_data_list_for_this_file, current_length_for_this_file_processing, flash_msg = \
                            _add_text_data_to_processed_list(
                                temp_processed_file_data_list_for_this_file, 
                                current_length_for_this_file_processing, 
                                attachment_data['content'],
                                attachment_data.get('filename', 'unknown_attachment'),
                                f"attachment from EML: {filename}"
                            )
                        if flash_msg: flash_messages.append(flash_msg)
                    elif attachment_data.get('type') == 'vision':
                        # Vision attachments are added directly to processed_entries
                        processed_entries.append(attachment_data) 
                    elif attachment_data.get('type') == 'error' or attachment_data.get('type') == 'unsupported':
                        processed_entries.append(attachment_data)
        
        elif processed_info.get('type') == 'text' and processed_info.get('content'):
            temp_processed_file_data_list_for_this_file, current_length_for_this_file_processing, flash_msg = \
                _add_text_data_to_processed_list(
                    temp_processed_file_data_list_for_this_file, 
                    current_length_for_this_file_processing, 
                    processed_info['content'], 
                    filename, 
                    "file content"
                )
            if flash_msg: flash_messages.append(flash_msg)
        elif processed_info.get('type') == 'vision':
            processed_entries.append(processed_info) # Add vision files directly
        
        # Add text data accumulated for this file to the main processed_entries
        processed_entries.extend(temp_processed_file_data_list_for_this_file)
        # Calculate how much new text length was actually added by this file's content
        text_length_added_by_this_file = current_length_for_this_file_processing - current_total_extracted_text_length

    except Exception as e:
        logger.error(f"Error saving or processing file {filename}: {e}", exc_info=True)
        flash_messages.append((f"An unexpected error occurred while processing file {filename}. It has been skipped. Please check logs for details.", "error"))
        processed_entries.append({'type': 'error', 'filename': filename, 'message': 'An unexpected error occurred during processing. Please see logs.'})

    return processed_entries, text_length_added_by_this_file, flash_messages, successfully_saved_filename

@app.route('/upload', methods=['POST'])
async def upload_files() -> Union[str, FlaskResponse]:
    # Explicitly use the app's logger
    app_logger = logging.getLogger(__name__) # or app.logger
    app_logger.info(f"!!!!!!!!!!!!!! ENTERED /upload route. Request ID: {g.get('request_id', 'N/A_upload_entry')} !!!!!!!!!!!!!!")
    app_logger.debug(f"Request Method: {request.method}")
    app_logger.debug(f"Request Headers: {list(request.headers)}") # Convert to list for better logging
    app_logger.debug(f"Request Form Data: {request.form.to_dict()}") # Convert to dict
    app_logger.debug(f"Request Files: {request.files.to_dict()}") # Convert to dict

    if 'files[]' not in request.files:
        app_logger.warning(f"!!!!!!!!!!!!!! File part 'files[]' missing in request. Request ID: {g.get('request_id', 'N/A_upload_no_files_part')} !!!!!!!!!!!!!!")
        flash("No file part in the request. Please select files to upload.", "error")
        # It's generally better to redirect to a GET route, like the index page, after a POST error.
        # return redirect(request.url) # request.url would be '/upload'
        return redirect(url_for('index'))

    files: List[FileStorage] = request.files.getlist('files[]')
    app_logger.info(f"!!!!!!!!!!!!!! Files received in 'files[]': {[f.filename for f in files]}. Request ID: {g.get('request_id', 'N/A_upload_files_list')} !!!!!!!!!!!!!!")

    validation_error = _validate_file_list(files)
    if validation_error:
        flash(validation_error[0], validation_error[1])
        return redirect(request.url)

    processed_file_data: List[Dict[str, Any]] = []
    uploaded_filenames_for_display: List[str] = []
    temp_dir: Union[str, None] = None # Changed from = "" to allow None check
    total_upload_size = 0
    current_total_extracted_text_length = 0

    try:
        # Calculate total upload size first
        for file_storage in files:
            if file_storage and file_storage.filename:
                file_storage.seek(0, os.SEEK_END)
                total_upload_size += file_storage.tell()
                file_storage.seek(0) # Reset cursor for subsequent reads
            else:
                # This case handles if a FileStorage object is somehow None or has no filename
                # It might be an empty part of the form, effectively skipping it.
                pass 

        if total_upload_size > settings.MAX_TOTAL_UPLOAD_SIZE_BYTES:
            logger.warning(f"Total upload size {total_upload_size} bytes exceeds limit of {settings.MAX_TOTAL_UPLOAD_SIZE_BYTES} bytes.")
            flash(f"Total upload size exceeds the limit of {settings.MAX_TOTAL_UPLOAD_SIZE_MB} MB.", "error")
            return redirect(request.url)

        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")

        logger.info(f"Starting processing of {len(files)} files. Request ID: {g.get('request_id', 'N/A_upload_processing_start')}")
        num_successful_processing = 0
        num_failed_processing = 0

        for file_storage in files:
            if not file_storage or not file_storage.filename: # Skip empty/invalid FileStorage objects
                num_failed_processing += 1
                continue
            
            # Individual file size check
            # Must read current position, go to end, read again, then reset.
            start_pos = file_storage.tell()
            file_storage.seek(0, os.SEEK_END)
            current_file_size = file_storage.tell()
            file_storage.seek(start_pos) # Reset to original position before this check
            
            if current_file_size > settings.MAX_FILE_SIZE_BYTES:
                logger.warning(f"File {file_storage.filename} size {current_file_size} bytes exceeds single file limit of {settings.MAX_FILE_SIZE_BYTES} bytes.")
                flash(f"File {file_storage.filename} exceeds the size limit of {settings.MAX_FILE_SIZE_MB} MB and was skipped.", "warning")
                processed_file_data.append({
                    'type': 'error',
                    'filename': file_storage.filename,
                    'message': f'File exceeds size limit of {settings.MAX_FILE_SIZE_MB} MB'
                })
                num_failed_processing += 1
                continue
            
            # Call the helper for actual processing
            entries, text_added, f_messages, saved_fname = await _process_single_file_storage(
                file_storage,
                temp_dir,
                current_total_extracted_text_length
            )
            processed_file_data.extend(entries)
            current_total_extracted_text_length += text_added
            for fm in f_messages:
                flash(fm[0], fm[1])
            if saved_fname:
                uploaded_filenames_for_display.append(saved_fname)
                num_successful_processing += 1
            else: # Implies an error occurred within _process_single_file_storage or was unsupported
                # Check if already counted as error due to size limit
                was_size_error = any(entry.get('filename') == file_storage.filename and 'File exceeds size limit' in entry.get('message', '') for entry in processed_file_data)
                if not was_size_error: # Avoid double counting if already handled by size check
                    num_failed_processing += 1

        logger.info(f"Finished processing files. {num_successful_processing} succeeded, {num_failed_processing} failed. Request ID: {g.get('request_id', 'N/A_upload_processing_end')}")

        if not processed_file_data and not uploaded_filenames_for_display:
             logger.warning("No files were suitable for processing after filtering. All might have been skipped due to size/type or were invalid.")
             flash("No files were suitable for processing.", "warning")
             return redirect(request.url)

        report_content: str = await llm_handler.generate_report_from_content(
            processed_files=processed_file_data,
            additional_text=""
        )

        if not report_content or report_content.strip().startswith("ERROR:"):
            logger.error(f"LLM Error: {report_content}")
            flash(f"Could not generate report: {report_content}", "error")
            return render_template('index.html', filenames=uploaded_filenames_for_display) 

        return render_template('report.html', report_content=report_content, filenames=uploaded_filenames_for_display)

    except Exception as e:
        logger.error(f"Unexpected error in upload_files: {e}", exc_info=True)
        flash("An unexpected server error occurred.", "error")
        return redirect(url_for('index'))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                await asyncio.to_thread(shutil.rmtree, temp_dir)
                logger.info(f"Successfully removed temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Error removing temporary directory {temp_dir}: {e}", exc_info=True)

@app.route('/download_report', methods=['POST'])
def download_report() -> Union[FlaskResponse, Tuple[str, int]]:
    report_content: Union[str, None] = request.form.get('report_content')
    if not report_content:
        return "Error: No report content to download.", 400

    try:
        file_stream: io.BytesIO = docx_generator.create_styled_docx(report_content)
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_filename: str = f"Insurance_Report_{timestamp}.docx"
        
        return send_file(
            file_stream,
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        logger.error(f"Error generating DOCX: {e}", exc_info=True)
        return f"Error generating DOCX: An unexpected error occurred.", 500

if __name__ == '__main__':
    app.run(debug=True) 