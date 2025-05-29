import os
import fitz  # PyMuPDF for PDFs - still used for basic validation or if needed for non-AI tasks
# import pytesseract # For OCR - No longer needed for PDF/image text extraction by LLM
from PIL import Image # For image handling - potentially for validation, no longer for OCR
from docx import Document as DocxDocument
import openpyxl # For XLSX files
import io
from typing import List, Union, Callable, Any, TypeVar, Dict # Added Dict
import logging
import functools
import mimetypes # Added for MIME type guessing

logger = logging.getLogger(__name__)

# pytesseract.pytesseract.tesseract_cmd = r'<full_path_to_your_tesseract_executable>' # No longer needed

F = TypeVar('F', bound=Callable[..., Any])

def handle_extraction_errors(default_return_value: Any = None) -> Callable[[F], F]: # Modified default
    """Decorator to handle common exceptions during file processing."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(file_path: str, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(file_path, *args, **kwargs)
            except FileNotFoundError:
                logger.error(f"File not found: {file_path}")
                return {'type': 'error', 'filename': os.path.basename(file_path), 'message': 'File not found'}
            # TesseractError no longer primary concern for LLM path
            # except pytesseract.TesseractError as te:
            #     logger.error(f"Tesseract OCR error for {file_path}: {te}", exc_info=True)
            #     return default_return_value
            except Image.UnidentifiedImageError:
                logger.error(f"Cannot identify image file: {file_path}", exc_info=True)
                return {'type': 'error', 'filename': os.path.basename(file_path), 'message': 'Cannot identify image file'}
            except openpyxl.utils.exceptions.InvalidFileException as ofe:
                logger.error(f"Invalid Excel (openpyxl) file format for {file_path}: {ofe}", exc_info=True)
                return {'type': 'error', 'filename': os.path.basename(file_path), 'message': f'Invalid Excel file: {ofe}'}
            except Exception as e:
                logger.error(f"Unexpected error processing {file_path} with {func.__name__}: {e}", exc_info=True)
                return {'type': 'error', 'filename': os.path.basename(file_path), 'message': f'Unexpected error: {e}'}
        return wrapper # type: ignore
    return decorator

# PDF and Image "extraction" functions will now just return file info for the LLM
@handle_extraction_errors()
def prepare_pdf_for_llm(pdf_path: str) -> Dict[str, str]:
    """Prepares PDF file information for LLM processing."""
    # Basic validation: can it be opened?
    try:
        doc = fitz.open(pdf_path)
        doc.close()
    except Exception as e:
        logger.error(f"PDF file {pdf_path} is likely corrupted or not a valid PDF: {e}")
        raise # Re-raise to be caught by decorator
    return {'type': 'vision', 'path': pdf_path, 'mime_type': 'application/pdf', 'filename': os.path.basename(pdf_path)}

@handle_extraction_errors()
def prepare_image_for_llm(image_path: str) -> Dict[str, str]:
    """Prepares image file information for LLM processing."""
    # Basic validation: can it be opened by PIL?
    try:
        img = Image.open(image_path)
        img.close()
    except Exception as e:
        logger.error(f"Image file {image_path} is likely corrupted or not a valid image: {e}")
        raise # Re-raise
    
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith('image/'):
        logger.warning(f"Could not determine a valid image MIME type for {image_path}, defaulting to application/octet-stream.")
        mime_type = 'application/octet-stream' # Fallback, though Gemini might reject
    return {'type': 'vision', 'path': image_path, 'mime_type': mime_type, 'filename': os.path.basename(image_path)}

@handle_extraction_errors({'type': 'text', 'content': '', 'filename': ''}) # filename will be overwritten
def extract_text_from_docx(docx_path: str) -> Dict[str, str]:
    """Extracts text from a DOCX file."""
    doc = DocxDocument(docx_path)
    full_text: List[str] = [para.text for para in doc.paragraphs]
    return {'type': 'text', 'content': '\n'.join(full_text), 'filename': os.path.basename(docx_path)}

@handle_extraction_errors({'type': 'text', 'content': '', 'filename': ''}) # filename will be overwritten
def extract_text_from_xlsx(xlsx_path: str) -> Dict[str, str]:
    """Extracts text from an XLSX file, converting sheets to CSV-like text."""
    text_content: str = ""
    workbook = openpyxl.load_workbook(xlsx_path)
    for sheet_name in workbook.sheetnames:
        text_content += f"--- Sheet: {sheet_name} ---\n"
        sheet = workbook[sheet_name]
        for row in sheet.iter_rows():
            row_values: List[str] = [str(cell.value) if cell.value is not None else "" for cell in row]
            text_content += ",".join(row_values) + "\n"
        text_content += "\n"
    workbook.close()
    return {'type': 'text', 'content': text_content, 'filename': os.path.basename(xlsx_path)}

@handle_extraction_errors({'type': 'text', 'content': '', 'filename': ''}) # filename will be overwritten
def extract_text_from_txt(txt_path: str) -> Dict[str, str]:
    """Extracts text from a TXT file."""
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return {'type': 'text', 'content': content, 'filename': os.path.basename(txt_path)}

def process_uploaded_file(filepath: str) -> Dict[str, Any]:
    """Determines file type and calls the appropriate processing function."""
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    filename: str = os.path.basename(filepath) # Moved here for all return paths

    processing_function: Union[Callable[[str], Dict[str, Any]], None] = None

    if ext == '.pdf':
        processing_function = prepare_pdf_for_llm
    elif ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']: # Added more image types
        processing_function = prepare_image_for_llm
    elif ext == '.docx':
        processing_function = extract_text_from_docx
    elif ext == '.xlsx':
        processing_function = extract_text_from_xlsx
    elif ext == '.txt':
        processing_function = extract_text_from_txt
    else:
        logger.warning(f"Unsupported file type: {ext} for file {filepath}")
        return {'type': 'unsupported', 'filename': filename, 'message': f'Unsupported file type: {ext}'}

    if processing_function:
        result = processing_function(filepath)
        # Ensure filename is in result, especially if decorator returned default
        if 'filename' not in result or not result['filename']:
            result['filename'] = filename
        return result
    
    # Should not be reached if logic is correct, but as a fallback:
    logger.error(f"No processing function determined for {filepath}, though extension seemed supported.")
    return {'type': 'error', 'filename': filename, 'message': 'Internal error: No processing function found.'} 