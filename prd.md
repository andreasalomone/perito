Okay, this is a great set of requirements and constraints. Here's a Product Requirements Document (PRD) for your LLM-powered Insurance Report Generator, incorporating all the provided information.

## Product Requirements Document: AI Insurance Report Generator

**1. Introduction**

*   **1.1 Purpose:** This document outlines the requirements for an AI-powered application designed to assist insurance professionals in rapidly generating professional, high-quality insurance reports in Italian. The application will leverage the OpenAI GPT-4o model to process uploaded documents and produce a structured report, which users can then review, edit, and download.
*   **1.2 Scope:** The initial version of this product will focus on accepting common document formats, extracting relevant information, generating a report based on a predefined style and structure, allowing user edits, and exporting to DOCX.
*   **1.3 Goals:**
    *   Significantly reduce the time and effort required to create detailed insurance reports.
    *   Ensure consistency and professionalism in report output by adhering to a specific style and format.
    *   Provide a user-friendly interface for document upload, report preview, and editing.
    *   Improve the overall efficiency of the insurance reporting workflow.
*   **1.4 Target Model:** OpenAI GPT-4o.

**2. Target Users**

*   Insurance Adjusters
*   Claims Handlers
*   Insurance Surveyors
*   Legal professionals working with insurance claims
*   Any professional requiring the generation of standardized insurance reports in Italian.

**3. User Stories**

*   **US1 (Document Upload):** As an insurance professional, I want to upload multiple documents (PNG, JPEG, other common image formats, XLSX, PDF, DOCX, TXT) related to a case, so that the system can extract information from them.
*   **US2 (Report Generation):** As an insurance professional, I want the system to automatically read the uploaded documents and generate a draft insurance report in Italian, adhering to a specific professional style and structure, so that I have a strong starting point for my final report.
*   **US3 (Report Preview & Edit):** As an insurance professional, I want to preview the generated report content in a clean interface and be able to easily edit the text, so that I can make necessary corrections, additions, or refinements.
*   **US4 (Report Download):** As an insurance professional, I want to download the final edited report in DOCX format, maintaining the professional formatting, so that I can submit it or store it.
*   **US5 (Efficiency):** As an insurance professional, I want to generate a complete and accurate insurance report in the least time possible, so that I can improve my productivity.

**4. Product Features**

*   **4.1 Document Upload Module:**
    *   Supports multi-file uploads.
    *   Supported file types:
        *   Images: PNG, JPEG/JPG, (consider TIFF, BMP if common)
        *   Spreadsheets: XLSX
        *   Documents: PDF (searchable and image-based), DOCX
        *   Text: TXT
    *   Clear feedback on upload progress and success/failure.
    *   Basic validation (e.g., file type, perhaps size limits).
*   **4.2 Document Processing & Information Extraction:**
    *   Backend service to convert all uploaded documents into a text format suitable for LLM processing.
        *   OCR for image files and image-based PDFs.
        *   Text extraction for DOCX, TXT, searchable PDFs.
        *   Data extraction from XLSX (potentially converting relevant sheets/tables to CSV-like text for the LLM).
    *   Consolidation of extracted text from multiple documents into a coherent input for the LLM.
*   **4.3 LLM-Powered Report Generation:**
    *   Integration with OpenAI GPT-4o API.
    *   **Prompt Engineering:**
        *   System prompt will instruct the LLM to act as an expert insurance report writer.
        *   The core instruction will be to generate a professional insurance report in **Italian**.
        *   The `PREDEFINED_STYLE_REFERENCE_TEXT` (provided in the prompt) will be heavily referenced to guide tone, phrasing, and terminology.
        *   The structure of the report will be guided by the provided sample document (e.g., sections like "DATI DELLA SPEDIZIONE", "DINAMICA DEGLI EVENTI ED ACCERTAMENTI", etc.). The LLM should be prompted to identify and populate these (or similar relevant) sections based on the input documents.
        *   **Strict Output Format:** The LLM must be explicitly instructed to output **plain text only**, with **no markdown whatsoever** (e.g., no `**bold**`, no `*italics*`, no `# headers`). Paragraphs should be separated by double line breaks (`\n\n`). Lists should be plain text lines, each starting with a hyphen or number if appropriate, followed by a space.
    *   The LLM will synthesize information from the processed documents to populate the report sections.
*   **4.4 Report Preview & Editing Interface:**
    *   A clean, intuitive web interface to display the LLM-generated plain text report.
    *   A text editing area (e.g., a `<textarea>` or a simple rich text editor configured for plain text-like input initially, focusing on respecting line breaks and basic structure) allowing users to modify the content.
    *   Changes should be easily saved/updated.
*   **4.5 Report Download (DOCX):**
    *   Functionality to convert the (edited) plain text report into a DOCX file.
    *   The DOCX generation will apply styling to match the visual structure and formatting of the provided sample report. This means:
        *   Specific headers (e.g., "DATI DELLA SPEDIZIONE") will be formatted (e.g., bolded, specific font size) by the DOCX generation logic, not by LLM markdown.
        *   Layout elements like the Salomone & ASSOCIATI header, address blocks, date, "Oggetto:", and footers from the sample will be programmatically added to the DOCX template.
        *   The LLM-generated content will be inserted into the appropriate sections of this DOCX template.

**5. User Flow Diagram**

```mermaid
graph TD
    A[User visits application] --> B{Start New Report};
    B --> C[Upload Documents <br>(PNG, JPG, XLSX, PDF, DOCX, TXT)];
    C --> D{All Documents Uploaded?};
    D -- Yes --> E[System Processes Documents <br>(OCR, Text Extraction)];
    E --> F[System Sends Data to LLM (GPT-4o) <br>with Style & Structure Prompts];
    F --> G[LLM Generates Report <br>(Italian, Plain Text, No Markdown)];
    G --> H[Display Report Draft in Preview/Edit Interface];
    H --> I{User Edits Report?};
    I -- Yes --> J[User Modifies Text];
    J --> H;
    I -- No / Finished Editing --> K[User Clicks 'Download Report'];
    K --> L[System Generates DOCX <br> (Applying Sample Report Formatting)];
    L --> M[User Downloads DOCX File];
```

**6. Design and UX Considerations**

*   **Simplicity and Intuitiveness:** The UI should be straightforward, guiding the user through the steps with minimal friction.
*   **Report Template Adherence (Visual):** While the LLM produces plain text, the final DOCX output must visually mirror the provided sample report. This involves:
    *   **Static Elements:** Header (logo, company name), footer (address, contact info, page number), "Spett.le" address block. These will be part of the DOCX template.
    *   **Dynamic Sections from LLM:** The plain text generated by the LLM for sections like "Oggetto:", "DATI DELLA SPEDIZIONE", "DINAMICA DEGLI EVENTI ED ACCERTAMENTI", "COMPUTO DEL DANNO", "CAUSE DEL DANNO" will be styled (e.g., bold headings, paragraph formatting) during DOCX generation.
*   **Editing Experience:** The editor should be responsive and allow for easy text manipulation. Focus on preserving line breaks which are crucial for plain text structure.
*   **Feedback:** Provide clear status indicators during document processing, LLM generation, and DOCX creation.
*   **Error Handling:** Gracefully handle errors (e.g., unsupported file type, failed OCR, LLM API error) with informative messages to the user.

**7. Technical Considerations**

*   **7.1 Backend:**
    *   Language/Framework: Python (Flask/Django recommended due to extensive libraries for document processing and OpenAI integration).
    *   API Design: RESTful APIs for frontend-backend communication.
*   **7.2 Frontend:**
    *   Framework: React, Vue, or Angular.
*   **7.3 Document Processing Libraries:**
    *   PDF: `PyMuPDF (fitz)`, `pdfplumber` for text and data.
    *   Images (OCR): `pytesseract` (wrapper for Tesseract OCR engine).
    *   DOCX: `python-docx` for reading.
    *   XLSX: `openpyxl` or `pandas` for reading.
*   **7.4 LLM Integration:**
    *   OpenAI Python client library.
    *   Robust prompt management and versioning.
    *   Handling API rate limits and errors.
*   **7.5 DOCX Generation:**
    *   `python-docx` for creating and styling the DOCX file.
    *   A base DOCX template might be used, or the document constructed entirely from code, applying styles defined to match the sample.
*   **7.6 Architecture:**
    *   Initial: Modular Monolith.
    *   Future: Could evolve to microservices if scaling needs demand it (e.g., separate service for document processing/OCR).
    *   Adherence to SOLID, KISS, DRY, YAGNI principles as outlined in the provided coding guidelines.
*   **7.7 Asynchronous Processing:** Document processing and LLM generation can be time-consuming. Implement asynchronous tasks (e.g., using Celery with Redis/RabbitMQ) to avoid blocking the UI.

**8. Non-Functional Requirements**

*   **8.1 Performance:**
    *   Document upload: Quick and responsive.
    *   Report generation: Target < 30-60 seconds for typical cases after document processing, dependent on document complexity and LLM response time. User should be informed if it's a longer process.
    *   DOCX download: Fast generation.
*   **8.2 Scalability:** The system should be designed to handle an increasing number of users and reports, particularly the backend processing tasks.
*   **8.3 Reliability:**
    *   High uptime.
    *   Consistent quality of LLM output given similar inputs.
    *   Robust error handling and recovery.
*   **8.4 Security:**
    *   Secure handling of uploaded documents (e.g., encryption at rest, access controls).
    *   Secure storage and use of OpenAI API keys.
    *   Protection against common web vulnerabilities (OWASP Top 10).
*   **8.5 Maintainability:**
    *   Codebase must adhere strictly to the comprehensive "Coding Guidelines" provided (SOLID, KISS, DRY, YAGNI, language-specific guidelines for Python, JS, HTML, CSS, API Client, etc.). This is paramount for long-term development and maintenance.
    *   Well-documented code and APIs.
    *   Modular design.
*   **8.6 Usability:** The application must be easy to learn and use for the target audience.

**9. Success Metrics**

*   **9.1 Task Completion Rate:** Percentage of users successfully generating and downloading a report.
*   **9.2 Time to Generate Report:** Average time taken by users from upload to download.
*   **9.3 User Satisfaction:** Measured via surveys or feedback forms (e.g., Net Promoter Score, CSAT).
*   **9.4 Adoption Rate:** Number of active users / reports generated per period.
*   **9.5 Reduction in Manual Effort:** Qualitative feedback on time saved compared to manual processes.

**10. Future Considerations (Post-MVP)**

*   Support for more document formats.
*   User accounts and report history.
*   Advanced editing features (e.g., AI-assisted rewriting of sections, grammar/style suggestions within the editor).
*   Customizable report templates/styles.
*   Direct integration with other insurance management systems.
*   Batch processing of reports.
*   Analytics on report generation.
*   Support for other languages.

**11. Out of Scope (For MVP)**

*   User authentication and management.
*   Collaboration features.
*   Advanced analytics dashboards.
*   Mobile application.
*   Direct editing of source documents (e.g., PDF annotation).

**12. Appendices**

*   **12.1 Appendix A: Reference Style and Terminology Prompt**
    *   (Include the full `PREDEFINED_STYLE_REFERENCE_TEXT` here.)
    ```
    PREDEFINED_STYLE_REFERENCE_TEXT = """
    **ESEMPI DI STILE E TERMINOLOGIA PER PERIZIE TECNICHE - SALOMONE & ASSOCIATI SRL**

    **NOTA PER L'LLM:** Questo testo fornisce esempi di tono di voce, fraseggio e terminologia specifica. Utilizzalo come guida
    per scrivere il contenuto testuale dettagliato e professionale richiesto per popolare i vari campi informativi della perizia.
    La struttura generale del report e i campi specifici da compilare ti verranno indicati separatamente.
    **Il materiale documentale fornito potrebbe includere dati estratti da fogli di calcolo, presentati come testo in formato CSV
    (valori separati da virgole), delimitati da marcatori che indicano il file e il foglio di origine.
    Presta attenzione a questi blocchi per estrarre informazioni tabellari o quantitative.**

    **Write plain text only; do **not** wrap words in **markdown** bold markers.**

    **1. Tono di Voce Generale:**
        *   **Professionale e Autorevole:** Mantieni un registro formale, preciso, oggettivo e altamente dettagliato.
        *   **Chiarezza:** Esprimi i concetti in modo inequivocabile, anche quando tecnici.
        *   **Linguaggio:** Evita colloquialismi o espressioni informali.

    **2. Struttura delle Frasi e Connettivi (Esempi da emulare nel testo generato):**
        *   Privilegia frasi complete e ben articolate.
        *   Utilizza connettivi logici per fluidità:
            *   "A seguito del gradito incarico conferitoci in data..."
            *   "Prendevamo quindi contatto con..."
            *   "Venivamo così informati che in data..."
            *   "Nella fattispecie ci veniva riferito che..."
            *   "Contestualmente si provvedeva a..."
            *   "Dall'esame della documentazione versata in atti e a seguito del sopralluogo effettuato..."
            *   "Una volta apprese le preliminari informazioni..."
            *   "Al momento del nostro intervento, si riscontrava..."
            *   "Stante quanto sopra esposto e considerata l'entità dei danni..."
            *   "In considerazione di quanto precede e sulla base degli elementi raccolti..."
            *   "Pertanto, si procedeva alla..."
            *   "Conseguentemente, si ritiene che..."
            *   "Per completezza espositiva, si precisa che..."

    **3. Terminologia Tecnica Specifica (Esempi da incorporare):**
        *   **Riferimenti Generali:** "incarico peritale", "accertamenti tecnici", "dinamica del sinistro", "risultanze peritali",
            "verbale di constatazione", "documentazione fotografica", "valore a nuovo", "valore commerciale ante-sinistro",
            "costi di ripristino", "franchigia contrattuale", "scoperto".
        *   **Parti Coinvolte:** "la Mandante", "la Ditta Assicurata", "il Contraente di polizza", "il Legale Rappresentante",
            "il Conducente del mezzo", "i Terzi danneggiati".
        *   **Documenti:** "polizza assicurativa n°...", "condizioni generali e particolari di polizza",
            "fattura di riparazione n°... del...", "preventivo di spesa", "libretto di circolazione", "certificato di proprietà".
        *   **Danni (specificare la natura):** "danni materiali diretti", "danni da urto", "danni da bagnamento",
            "danni da incendio", "deformazione strutturale", "rottura cristalli", "ammaccature", "graffiature profonde".
        *   **Veicoli:** "trattore stradale", "semirimorchio", "autovettura", "motoveicolo", "numero di telaio (VIN)",
            "targa di immatricolazione".

    **4. Formattazione del Testo Generato per Campi Narrativi (es. `dinamica_eventi`, `accertamenti`, `quantificazione`,
    `commento`):**
        *   **Paragrafi:** Separa i paragrafi logici con due interruzioni di riga (`\\n\\n`). Ogni paragrafo dovrebbe sviluppare
            un punto specifico in modo dettagliato.
        *   **Grassetto (`**testo**`):** Utilizzare con estrema parsimonia, solo per enfatizzare termini tecnici cruciali o importi
            monetari particolarmente significativi all'interno di una frase, se strettamente necessario per la chiarezza.
            Non usare per titoli o sottotitoli.
        *   **Elenchi Puntati:** Per la sezione dedicata alla quantificazione dei danni (e se necessario in quella degli accertamenti
            per elencare i danni), utilizzare elenchi puntati chiari per voci di costo, parti danneggiate, o documenti esaminati.
            *Esempio per costi:*
            `- Ricambi originali: € 1.234,56`
            `- Manodopera (X ore a € Y/ora): € ZZZ,ZZ`
            `- Materiali di consumo: € AA,BB`
        *   **Valute e Numeri:**
            *   Valute: `€ 1.234,56` (spazio tra € e cifra; punto per migliaia; virgola per decimali).
            *   Date nel corpo del testo: `GG/MM/AAAA`.

    **5. Lunghezza e Dettaglio (per i campi narrativi):**
        *   Le sezioni narrative principali della perizia (come la dinamica dell'evento, gli accertamenti svolti, la quantificazione
            dei danni e il commento finale) devono essere redatte in modo esteso e particolareggiato, almeno 500 parole per ogni sezione.
            Chi legge vuole ricevere un report molto grande, così che aumenta la percezione di valore (molto importante).
            Questo testo di riferimento stilistico serve a garantire che tale estensione sia riempita
            con linguaggio appropriato, preciso e professionale, aderente agli standard qualitativi richiesti.

    **Esempio di Fraseggio da Emulare (per tono e dettaglio):**
        "Dall'esame della documentazione fornita dalla Mandante, specificatamente la polizza n° [NumeroPolizza] e la denuncia
        di sinistro, nonché a seguito del sopralluogo tecnico effettuato in data [DataSopralluogo] presso i locali della Ditta
        Assicurata siti in [Luogo], assistiti dal Sig. [NomeReferenteAssicurato], Responsabile di [RuoloReferenteAssicurato],
        è stato possibile ricostruire la dinamica dell'evento e constatare l'effettiva entità dei danni patiti."

        "Gli accertamenti peritali si sono quindi concentrati sulla verifica analitica delle componenti danneggiate del
        [bene danneggiato], sulla disamina delle cause che hanno originato il guasto/danno, e sulla congruità dei costi esposti
        nel preventivo di riparazione n° [NumeroPreventivo] emesso dalla ditta [NomeRiparatore]."

        "La quantificazione del danno, come analiticamente esposta nella sezione dedicata e basata sulla fattura di riparazione
        n° [NumeroFattura] del [DataFattura], ammonta a complessivi Euro [ImportoTotale],XX, al lordo di eventuali franchigie
        e/o scoperti come da condizioni della polizza [TipoPolizza] n° [NumeroPolizza]."

    Important: **Write plain text only; do **not** wrap words in **markdown** bold markers.**
    Do not output markdown asterisks. Paragraphs are separated by blank lines; lists by separate lines.
    """
    ```
*   **12.2 Appendix B: Sample Report Structure (Derived from OCR image)**
    *   (This section would ideally contain a more structured breakdown of the sample report's layout elements and how they map to LLM output and DOCX template fields. For brevity, it's summarized here, but a detailed mapping would be beneficial for developers.)
        *   **Header:** Salomone & ASSOCIATI SRL Logo and Name
        *   **Date & Origin:** Genova, [Date]
        *   **Internal References Block:**
            *   Vs. rif. [Value]
            *   Rif. broker : [Value]
            *   Polizza merci n. [Value]
            *   Ns. rif. [Value]
        *   **Recipient Address Block ("Spett.le"):**
            *   Talbot Underwriting Risk Services LTD
            *   [Address Lines]
            *   Vat no. [Value]
        *   **Subject ("Oggetto:"):**
            *   Assicurata: [Value]
            *   Danni da [Value] – Evento del [Date]
            *   Committente al trasporto: [Value]
        *   **Introductory Paragraph(s):** Text describing the assignment.
        *   **Main Section 1: "1. DATI DELLA SPEDIZIONE"**
            *   Shipment: [Details]
            *   Gross Weight: [Details]
            *   Shipper: [Details]
            *   Consignee: [Details]
            *   Policy no.: [Details]
            *   Contractual carrier: [Details]
            *   Insured / Real Carrier: [Details]
            *   CMR: [Details]
        *   **Main Section 2: "2 – DINAMICA DEGLI EVENTI ED ACCERTAMENTI"**
            *   Paragraphs describing events and findings.
        *   **(Other potential main sections like on page 3 and 4 of the sample):**
            *   "3- COMPUTO DEL DANNO" (Damage Calculation)
            *   "3 – CAUSE DEL DANNO" (Causes of Damage - Note: Sample has "3" twice, PRD should clarify if it's 3 & 4 or subsection)
        *   **Closing:** Salutations, "Salomone & Associati S.r.l."
        *   **Attachments List ("Allegati :")**
        *   **Footer:** Company full address, contact details, Fiscal Code, P.Iva, REA, PEC. Page number.

*   **12.3 Appendix C: Coding Guidelines**
    *   Reference to the externally provided comprehensive document containing:
        *   SOLID Principles
        *   KISS, DRY, YAGNI, POLA, Easy to Delete
        *   Code Readability and Maintainability
        *   Development Workflow & Quality Assurance (Incremental Dev, Testing, Git)
        *   Internal Behavioral Guidelines for AI Coding Assistant
        *   API Client Coding Guidelines
        *   Python Coding Guidelines (PEP 8, Type Hinting, Docstrings, etc.)
        *   HTML Coding Guidelines (Semantic, Accessibility, Validation, etc.)
        *   CSS Coding Guidelines (Naming, Modularity, Readability, etc.)
        *   JavaScript Coding Guidelines (ES6+, Modularity, Strict Mode, etc.)

This PRD should provide a solid foundation for the development team. The most critical aspects for the LLM interaction are the detailed style prompt and the strict "no markdown, plain text" output requirement, combined with a clear understanding of how that plain text will be mapped to a visually formatted DOCX using the sample report as a guide.