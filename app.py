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
    text_from_other_files: str = ""
    uploaded_filenames_for_display: List[str] = []
    temp_dir: Union[str, None] = None
    total_upload_size = 0

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
                    
                    processed_info: Dict[str, Any] = document_processor.process_uploaded_file(filepath)
                    processed_file_data.append(processed_info)

                    if processed_info.get('type') == 'text' and processed_info.get('content'):
                        extracted_text_part = processed_info['content']
                        text_header = f"--- START OF EXTRACTED TEXT FROM FILE: {filename} ---\n"
                        text_footer = f"\n--- END OF EXTRACTED TEXT FROM FILE: {filename} ---\n\n"
                        full_part_text = text_header + extracted_text_part + text_footer

                        if len(text_from_other_files) + len(full_part_text) > settings.MAX_EXTRACTED_TEXT_LENGTH:
                            logger.warning(f"Aggregated text from DOCX/XLSX/TXT reached limit of {settings.MAX_EXTRACTED_TEXT_LENGTH} characters. Further text from {filename} and subsequent files will be truncated/skipped.")
                            remaining_space = settings.MAX_EXTRACTED_TEXT_LENGTH - len(text_from_other_files)
                            text_from_other_files += full_part_text[:remaining_space]
                            flash(f"Combined text from non-PDF/image files is very large. Content from {filename} onwards might be truncated.", "warning")
                        else:
                            text_from_other_files += full_part_text

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
            additional_text=text_from_other_files
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