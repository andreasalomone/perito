from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn # Needed for page numbering
import io
import re
from typing import List
from datetime import datetime

from core.config import settings # Import new settings

def create_styled_docx(plain_text_report_content: str) -> io.BytesIO:
    """Creates a DOCX file from plain text, applying styling similar to the sample."""
    document: Document = Document()

    # Set default font for the document
    style = document.styles['Normal']
    font = style.font
    font.name = settings.DOCX_FONT_NAME
    font.size = Pt(settings.DOCX_FONT_SIZE_NORMAL)
    paragraph_format = style.paragraph_format
    paragraph_format.line_spacing = 1.5

    # --- Static Header Elements (as per Appendix B and config) ---
    # To remove headers from all pages, we comment out the header creation block.
    # header = document.sections[0].header
    # header_paragraph = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    # header_run = header_paragraph.add_run(settings.DOCX_HEADER_TEXT)
    # header_run.bold = True
    # header_run.font.size = Pt(settings.DOCX_FONT_SIZE_HEADING)
    # header_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # # Add some space after header or use paragraph spacing
    # header.add_paragraph() 

    # Date and Origin (PRD Appendix B)
    # Using a more specific date format as per typical Italian professional documents
    document.add_paragraph() # Spacer

    # Recipient Address Block (PRD Appendix B) - Placeholder
    document.add_paragraph() 

    # --- Processing LLM Content ---
    lines: List[str] = plain_text_report_content.split('\n')
    
    # Regex for main section titles (e.g., "1. SECTION NAME", "SECTION NAME:")
    # and "OGGETTO:" specifically.
    section_title_pattern = re.compile(
        r"^([0-9]+\.\s*)?([A-Z][A-Z0-9\s,()/-]+[A-Z0-9]):?$|^OGGETTO:"
    )
    # Regex for sub-items or list-like entries (starting with dash, asterisk, or number.dot)
    list_item_pattern = re.compile(r"^\s*([-*]|\d+\.)\s+", re.IGNORECASE)


    for line_num, line in enumerate(lines):
        stripped_line = line.strip()

        # Handle intentional double newlines from LLM for paragraph spacing
        if not stripped_line:
            if line_num > 0 and lines[line_num-1].strip(): # Avoid multiple blank paragraphs if LLM already did
                document.add_paragraph("")
            continue

        is_section_title = section_title_pattern.match(stripped_line)
        is_list_item = list_item_pattern.match(stripped_line)

        if is_section_title:
            p = document.add_paragraph()
            run = p.add_run(stripped_line)
            run.bold = True
            run.font.size = Pt(settings.DOCX_FONT_SIZE_HEADING)
            # Consider adding space_after property to paragraph_format for titles
            p.paragraph_format.space_after = Pt(6) 
        elif is_list_item:
            # More robust list handling might involve tracking list depth or using specific list styles.
            # For now, basic indentation.
            p = document.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            # If it's a numbered list item, python-docx handles numbering if style is 'ListNumber'
            # If it's a bullet, style is 'ListBullet'.
            # However, LLM provides plain text, so we add the bullet/number as text.
            p.add_run(stripped_line)

        else: # Regular paragraph
            # Add paragraph, ensuring not to add to the previous if it was a title (handled by space_after)
            # or if the current line is a continuation of a paragraph (needs more complex logic not implemented here)
            document.add_paragraph(stripped_line)
    
    document.add_paragraph("Restando comunque a disposizione per ulteriori chiarimenti che potessero necessitare cogliamo l'occasione per porgere distinti saluti. Salomone & Associati S.r.l.")
    
    # --- Static Footer Elements with Page Numbering ---
    footer = document.sections[0].footer
    footer_paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    
    # Add page number field
    # Create a run for the left part of the footer
    footer_run_text = footer_paragraph.add_run(settings.DOCX_FOOTER_TEXT_TEMPLATE.split('{page_number}')[0])
    footer_run_text.font.size = Pt(9)

    # Add PAGE field
    run = footer_paragraph.add_run()
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    run._r.append(fldChar1)

    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = "PAGE"
    run._r.append(instrText)

    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar2)
    
    # Add "di" and NUMPAGES field
    text_after_page_num = ""
    text_before_total_pages = ""
    text_after_total_pages = ""

    if '{page_number}' in settings.DOCX_FOOTER_TEXT_TEMPLATE:
        parts_around_page_num = settings.DOCX_FOOTER_TEXT_TEMPLATE.split('{page_number}', 1)
        if len(parts_around_page_num) > 1:
            text_after_page_num_part = parts_around_page_num[1]
            if '{total_pages}' in text_after_page_num_part:
                parts_around_total_pages = text_after_page_num_part.split('{total_pages}', 1)
                text_before_total_pages = parts_around_total_pages[0]
                if len(parts_around_total_pages) > 1:
                    text_after_total_pages = parts_around_total_pages[1]
            else:
                text_before_total_pages = text_after_page_num_part # No total_pages, so everything after page_num is before (non-existent) total_pages
        # If only {page_number} exists and it's at the end, text_before_total_pages remains empty
    elif '{total_pages}' in settings.DOCX_FOOTER_TEXT_TEMPLATE: # Only {total_pages} exists
        # This case is not directly handled by the original logic structure of adding PAGE first
        # For simplicity, if only {total_pages} is present, we might need a different field construction
        # Or, assume {page_number} is primary. If it's not present, complex logic for only {total_pages} is skipped by original flow.
        pass # Current logic prioritizes {page_number}

    if text_before_total_pages:
        run = footer_paragraph.add_run(text_before_total_pages)
        run.font.size = Pt(9)
    
    if '{total_pages}' in settings.DOCX_FOOTER_TEXT_TEMPLATE and \
       ('{page_number}' in settings.DOCX_FOOTER_TEXT_TEMPLATE and text_before_total_pages is not None): # Ensure total_pages is processed if it was expected
        
        run = footer_paragraph.add_run()
        fldChar1 = OxmlElement('w:fldChar')
        fldChar1.set(qn('w:fldCharType'), 'begin')
        run._r.append(fldChar1)

        instrText = OxmlElement('w:instrText')
        instrText.set(qn('xml:space'), 'preserve')
        instrText.text = "NUMPAGES"
        run._r.append(instrText)

        fldChar2 = OxmlElement('w:fldChar')
        fldChar2.set(qn('w:fldCharType'), 'end')
        run._r.append(fldChar2)

    if text_after_total_pages:
        run = footer_paragraph.add_run(text_after_total_pages)
        run.font.size = Pt(9)
    
    # If neither placeholder was in the template originally, but we added PAGE field, 
    # and the original template was just static text, that static text needs to be handled.
    # However, the first part of the template was already added before PAGE.
    # This revised logic tries to reconstruct based on placeholders.
    # If template had no placeholders at all, the first part (entire template) is added, then PAGE field.
    # If it had {page_number} but not {total_pages}, then parts_around_page_num[1] is added after PAGE.

    # Fallback for templates that didn't have {page_number} but might have text after where {total_pages} would be (or just static text)
    if '{page_number}' not in settings.DOCX_FOOTER_TEXT_TEMPLATE and '{total_pages}' not in settings.DOCX_FOOTER_TEXT_TEMPLATE:
        # The initial part of the footer (which is the whole template if no placeholders) 
        # was already added by: footer_run_text = footer_paragraph.add_run(settings.DOCX_FOOTER_TEXT_TEMPLATE.split('{page_number}')[0])
        # This line effectively adds the template again if no {page_number} was found. This might be redundant or handled by initial add.
        # Let's ensure the initial add covers the whole template if no {page_number}
        # The line `footer_run_text = footer_paragraph.add_run(settings.DOCX_FOOTER_TEXT_TEMPLATE.split('{page_number}')[0])`
        # correctly adds the whole template if {page_number} is not present.
        # So, no further action needed here for that case regarding the template text itself.
        pass 

    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Save to a BytesIO object
    file_stream: io.BytesIO = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream 