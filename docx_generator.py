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
    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Add "Page " text
    run = footer_paragraph.add_run("Page ")
    run.font.size = Pt(settings.DOCX_FONT_SIZE_FOOTER if hasattr(settings, 'DOCX_FONT_SIZE_FOOTER') else 9)

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
    
    # Add " of " text
    run = footer_paragraph.add_run(" of ")
    run.font.size = Pt(settings.DOCX_FONT_SIZE_FOOTER if hasattr(settings, 'DOCX_FONT_SIZE_FOOTER') else 9)

    # Add NUMPAGES field
    run = footer_paragraph.add_run()
    fldChar1_np = OxmlElement('w:fldChar')
    fldChar1_np.set(qn('w:fldCharType'), 'begin')
    run._r.append(fldChar1_np)

    instrText_np = OxmlElement('w:instrText')
    instrText_np.set(qn('xml:space'), 'preserve')
    instrText_np.text = "NUMPAGES"
    run._r.append(instrText_np)

    fldChar2_np = OxmlElement('w:fldChar')
    fldChar2_np.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar2_np)

    # Save to a BytesIO object
    file_stream: io.BytesIO = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream 