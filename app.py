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
from typing import List, Tuple, Union, Dict, Any
import io
import uuid
from flask import get_flashed_messages

from core.config import settings

load_dotenv()

app = Flask(__name__)

# --- Logging Configuration ---
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                    format='%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s')

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            # Attempt to get request_id from Flask's g object
            # g is only available in a request context
            record.request_id = g.get('request_id', 'N/A')
        except RuntimeError:
            # This occurs if logging happens outside of an app context (e.g. startup)
            # or request context.
            record.request_id = 'N/A_OUTSIDE_REQUEST'
        return True

logger = logging.getLogger(__name__)
# logger.addFilter(RequestIdFilter()) # This is now handled by applying to root handlers

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

@app.route('/')
def index() -> str:
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files() -> Union[str, FlaskResponse]:
    if 'files[]' not in request.files:
        logger.warning("File part missing in request.")
        flash("No file part in the request.", "error")
        return redirect(request.url)
    
    files: List[FileStorage] = request.files.getlist('files[]')
    
    if not files or all(f.filename == '' for f in files):
        logger.info("No files selected for uploading.")
        flash("No files selected for uploading.", "warning")
        return redirect(request.url)

    processed_file_data: List[Dict[str, Any]] = []
    uploaded_filenames_for_display: List[str] = []
    temp_dir: Union[str, None] = None
    total_upload_size = 0
    current_total_extracted_text_length = 0

    try:
        for file_storage in files:
            file_storage.seek(0, os.SEEK_END)
            total_upload_size += file_storage.tell()
            file_storage.seek(0)

        if total_upload_size > settings.MAX_TOTAL_UPLOAD_SIZE_BYTES:
            logger.warning(f"Total upload size {total_upload_size} bytes exceeds limit of {settings.MAX_TOTAL_UPLOAD_SIZE_BYTES} bytes.")
            flash(f"Total upload size exceeds the limit of {settings.MAX_TOTAL_UPLOAD_SIZE_MB} MB.", "error")
            return redirect(request.url)

        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")

        for file_storage in files:
            if file_storage.filename == '':
                continue
            
            current_file_size = file_storage.tell()
            file_storage.seek(0)
            if current_file_size > settings.MAX_FILE_SIZE_BYTES:
                logger.warning(f"File {file_storage.filename} size {current_file_size} bytes exceeds single file limit of {settings.MAX_FILE_SIZE_BYTES} bytes.")
                flash(f"File {file_storage.filename} exceeds the size limit of {settings.MAX_FILE_SIZE_MB} MB and was skipped.", "warning")
                processed_file_data.append({
                    'type': 'error',
                    'filename': file_storage.filename,
                    'message': f'File exceeds size limit of {settings.MAX_FILE_SIZE_MB} MB'
                })
                continue
            
            if allowed_file(file_storage.filename):
                filename: str = secure_filename(file_storage.filename)
                if not filename:
                    logger.warning(f"secure_filename resulted in empty filename for original: {file_storage.filename}, skipping.")
                    processed_file_data.append({
                        'type': 'error',
                        'filename': file_storage.filename,
                        'message': 'Invalid filename after securing.'
                    })
                    continue
                
                filepath: str = os.path.join(temp_dir, filename)
                try:
                    file_storage.save(filepath)
                    logger.info(f"Saved uploaded file to temporary path: {filepath}")
                    uploaded_filenames_for_display.append(filename)
                    
                    processed_info: Dict[str, Any] = document_processor.process_uploaded_file(filepath, temp_dir)
                    
                    def add_text_data_to_processed_list(
                        text_content: str, 
                        original_filename: str, 
                        source_description: str
                    ) -> None:
                        nonlocal current_total_extracted_text_length
                        if not text_content:
                            return

                        # Check if adding this text would exceed the limit
                        if current_total_extracted_text_length + len(text_content) > settings.MAX_EXTRACTED_TEXT_LENGTH:
                            remaining_space = settings.MAX_EXTRACTED_TEXT_LENGTH - current_total_extracted_text_length
                            if remaining_space > 0:
                                truncated_content = text_content[:remaining_space]
                                processed_file_data.append({
                                    'type': 'text',
                                    'content': truncated_content,
                                    'filename': f"{original_filename} ({source_description} - truncated)"
                                })
                                current_total_extracted_text_length += len(truncated_content)
                                logger.warning(f"Text from {original_filename} ({source_description}) was truncated due to total length limit.")
                                flash(f"Text from {original_filename} ({source_description}) was truncated to fit within the overall text limit.", "warning")
                            else:
                                logger.warning(f"No space left to add text from {original_filename} ({source_description}). It was skipped.")
                                flash(f"Text from {original_filename} ({source_description}) was skipped as the overall text limit was reached.", "warning")
                            # Once limit is hit (or no space for current item), can potentially stop adding more text.
                            # For now, we just skip or truncate this item and continue trying others.
                        else:
                            processed_file_data.append({
                                'type': 'text',
                                'content': text_content,
                                'filename': f"{original_filename} ({source_description})"
                            })
                            current_total_extracted_text_length += len(text_content)

                    if processed_info.get('type') == 'error' or processed_info.get('type') == 'unsupported':
                        processed_file_data.append(processed_info) # Add error/unsupported info directly
                    elif processed_info.get('original_filetype') == 'eml':
                        if processed_info.get('type') == 'text' and processed_info.get('content'):
                            add_text_data_to_processed_list(
                                processed_info['content'], 
                                filename, 
                                "email body"
                            )
                        
                        if 'processed_attachments' in processed_info and isinstance(processed_info['processed_attachments'], list):
                            for attachment_data in processed_info['processed_attachments']:
                                if attachment_data.get('type') == 'text' and attachment_data.get('content'):
                                    add_text_data_to_processed_list(
                                        attachment_data['content'],
                                        attachment_data.get('filename', 'unknown_attachment'),
                                        f"attachment from EML: {filename}"
                                    )
                                elif attachment_data.get('type') == 'vision':
                                    processed_file_data.append(attachment_data) # Add vision attachments directly
                                elif attachment_data.get('type') == 'error' or attachment_data.get('type') == 'unsupported':
                                    processed_file_data.append(attachment_data) # Add attachment errors directly
                    
                    elif processed_info.get('type') == 'text' and processed_info.get('content'):
                        add_text_data_to_processed_list(
                            processed_info['content'],
                            filename,
                            "file content" # Generic source for other text files
                        )
                    elif processed_info.get('type') == 'vision':
                         processed_file_data.append(processed_info) # Add vision files directly

                except Exception as e:
                    logger.error(f"Error saving or processing file {filename}: {e}", exc_info=True)
                    flash(f"Error processing file {filename}. It has been skipped.", "error")
                    processed_file_data.append({'type': 'error', 'filename': filename, 'message': f'Error saving/processing: {e}'})
            else:
                logger.warning(f"File type not allowed: {file_storage.filename}, skipping.")
                flash(f"File type not allowed for {file_storage.filename}. It has been skipped.", "warning")
                processed_file_data.append({'type': 'unsupported', 'filename': file_storage.filename, 'message': 'File type not allowed'})

        if not processed_file_data:
             logger.warning("No files were processed (e.g., all empty, all failed size checks before processing call). Redirecting.")
             flash("No files were suitable for processing.", "warning")
             return redirect(request.url)

        report_content: str = llm_handler.generate_report_from_content(
            processed_files=processed_file_data, 
            additional_text=""
        )

        if report_content.startswith("Error:"):
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
                shutil.rmtree(temp_dir)
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