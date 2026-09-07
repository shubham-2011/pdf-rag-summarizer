import os
import re
from typing import List, Tuple, Dict, Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from services.pdf_service import PDFService
import config

class DocumentService:
    """
    Universal Multi-Format Document Ingestion & Audit Service.
    Supports PDF (.pdf), Word (.docx, .doc), PowerPoint (.pptx, .ppt), Excel (.xlsx, .xls, .csv), and Text (.txt, .md).
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".txt", ".md"
    }

    @staticmethod
    def audit_document(file_path: str, file_size: int) -> Tuple[bool, str]:
        """Audits any supported document format against size, corruption, and text extractability constraints."""
        if file_size == 0:
            return False, "Uploaded file is empty (0 bytes)."
            
        if file_size > config.MAX_FILE_SIZE_BYTES:
            size_mb = round(file_size / (1024 * 1024), 2)
            return False, f"File size ({size_mb} MB) exceeds maximum allowed limit of {config.MAX_FILE_SIZE_MB} MB."

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in DocumentService.SUPPORTED_EXTENSIONS:
            return False, f"Unsupported file extension '{ext}'. Supported formats: PDF, DOCX, PPTX, XLSX, CSV, TXT, MD."

        if ext == ".pdf":
            return PDFService.audit_pdf(file_path, file_size)

        if ext == ".doc":
            return False, (
                "Legacy binary .doc format requires an external converter (LibreOffice or MS Word), "
                "which is not available in this environment. Please convert to .docx or .pdf."
            )

        if ext == ".docx":
            try:
                import docx
                doc = docx.Document(file_path)
                full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                for table in doc.tables:
                    for row in table.rows:
                        full_text += " " + " | ".join([cell.text.strip() for cell in row.cells])
                if len(full_text.strip()) < config.MIN_TEXT_CHARS:
                    return False, "Word document contains no extractable text."
                return True, "Word document audit passed."
            except Exception as e:
                return False, f"Invalid or corrupted Word document: {e}"

        if ext in [".pptx", ".ppt"]:
            try:
                from pptx import Presentation
                prs = Presentation(file_path)
                slide_count = len(prs.slides)
                if slide_count == 0:
                    return False, "PowerPoint presentation contains 0 slides."
                if slide_count > config.MAX_PAGE_COUNT:
                    return False, f"Presentation has {slide_count} slides, exceeding maximum limit of {config.MAX_PAGE_COUNT}."
                full_text = ""
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            full_text += " " + shape.text_frame.text.strip()
                if len(full_text.strip()) < config.MIN_TEXT_CHARS:
                    return False, "PowerPoint presentation contains no extractable text."
                return True, "PowerPoint presentation audit passed."
            except Exception as e:
                return False, f"Invalid or corrupted PowerPoint file: {e}"

        if ext in [".xlsx", ".xls", ".csv"]:
            try:
                import pandas as pd
                if ext == ".csv":
                    df = pd.read_csv(file_path, nrows=50)
                else:
                    df = pd.read_excel(file_path, nrows=50)
                if df.empty:
                    return False, "Spreadsheet is empty."
                return True, "Spreadsheet audit passed."
            except Exception as e:
                return False, f"Invalid or corrupted Spreadsheet: {e}"

        if ext in [".txt", ".md"]:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if len(content.strip()) < config.MIN_TEXT_CHARS:
                    return False, "Text document contains insufficient text content."
                return True, "Text document audit passed."
            except Exception as e:
                return False, f"Could not read text document: {e}"

        return False, "Unknown file format."

    @staticmethod
    def process_document(file_path: str, api_key: str = None) -> Tuple[List[Document], int]:
        """Parses and chunks any supported document type into semantic Document vectors."""
        ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)

        if ext == ".pdf":
            return PDFService.process_pdf(file_path, api_key=api_key)

        if ext == ".doc":
            raise ValueError(
                "Legacy binary .doc format requires an external converter (LibreOffice or MS Word), "
                "which is not available in this environment. Please convert to .docx or .pdf."
            )

        pages = []
        total_units = 1

        # 📄 1. Word Documents (.docx)
        if ext == ".docx":
            import docx
            doc = docx.Document(file_path)
            docx_blocks: List[Document] = []

            # 1. Section Headers & Footers
            for s_idx, section in enumerate(doc.sections):
                try:
                    if section.header and section.header.paragraphs:
                        h_texts = [p.text.strip() for p in section.header.paragraphs if p.text.strip()]
                        if h_texts:
                            docx_blocks.append(Document(
                                page_content=f"Header (Section {s_idx + 1}): " + " ".join(h_texts),
                                metadata={
                                    "source_file": file_name,
                                    "content_type": "word_document",
                                    "block_type": "header_footer",
                                    "section_heading": f"Header Section {s_idx + 1}",
                                    "unit_kind": "paragraph",
                                    "unit_name": "paragraphs",
                                    "paragraph_count": len(doc.paragraphs),
                                    "table_count": len(doc.tables),
                                    "page": 0,
                                    "page_label": 1
                                }
                            ))
                except Exception:
                    pass
                try:
                    if section.footer and section.footer.paragraphs:
                        f_texts = [p.text.strip() for p in section.footer.paragraphs if p.text.strip()]
                        if f_texts:
                            docx_blocks.append(Document(
                                page_content=f"Footer (Section {s_idx + 1}): " + " ".join(f_texts),
                                metadata={
                                    "source_file": file_name,
                                    "content_type": "word_document",
                                    "block_type": "header_footer",
                                    "section_heading": f"Footer Section {s_idx + 1}",
                                    "unit_kind": "paragraph",
                                    "unit_name": "paragraphs",
                                    "paragraph_count": len(doc.paragraphs),
                                    "table_count": len(doc.tables),
                                    "page": 0,
                                    "page_label": 1
                                }
                            ))
                except Exception:
                    pass

            # 2. Body Paragraphs with Heading Detection
            current_heading = "General"
            for p_idx, p in enumerate(doc.paragraphs):
                p_text = p.text.strip()
                if not p_text:
                    continue
                if p.style and p.style.name and p.style.name.startswith("Heading"):
                    current_heading = p_text
                docx_blocks.append(Document(
                    page_content=p_text,
                    metadata={
                        "source_file": file_name,
                        "content_type": "word_document",
                        "block_type": "paragraph",
                        "section_heading": current_heading,
                        "unit_kind": "paragraph",
                        "unit_name": "paragraphs",
                        "paragraph_count": len(doc.paragraphs),
                        "table_count": len(doc.tables),
                        "page": 0,
                        "page_label": 1
                    }
                ))

            # 3. Table Cells & Rows (grouped by row to maintain structure)
            for t_idx, table in enumerate(doc.tables):
                t_rows = []
                for r_idx, row in enumerate(table.rows):
                    row_data = [c.text.strip() for c in row.cells]
                    t_rows.append(" | ".join(row_data))
                if t_rows:
                    docx_blocks.append(Document(
                        page_content=f"Table {t_idx + 1}:\n" + "\n".join(t_rows),
                        metadata={
                            "source_file": file_name,
                            "content_type": "word_document",
                            "block_type": "table",
                            "table_index": t_idx + 1,
                            "section_heading": f"Table {t_idx + 1}",
                            "unit_kind": "paragraph",
                            "unit_name": "paragraphs",
                            "paragraph_count": len(doc.paragraphs),
                            "table_count": len(doc.tables),
                            "page": 0,
                            "page_label": 1
                        }
                    ))

            # 4. Text Boxes & Shapes (walk Word XML)
            try:
                for tb_idx, txbx in enumerate(doc.element.xpath('//*[local-name()="txbxContent"]')):
                    tb_text = " ".join("".join(txbx.itertext()).split()).strip()
                    if tb_text:
                        docx_blocks.append(Document(
                            page_content=f"Callout / Text Box: {tb_text}",
                            metadata={
                                "source_file": file_name,
                                "content_type": "word_document",
                                "block_type": "text_box",
                                "section_heading": "Text Box",
                                "unit_kind": "paragraph",
                                "unit_name": "paragraphs",
                                "paragraph_count": len(doc.paragraphs),
                                "table_count": len(doc.tables),
                                "page": 0,
                                "page_label": 1
                            }
                        ))
            except Exception:
                pass

            pages.extend(docx_blocks)
            total_units = len(doc.paragraphs)


        # 📊 2. PowerPoint Presentations (.pptx)
        elif ext in [".pptx", ".ppt"]:
            from pptx import Presentation
            prs = Presentation(file_path)
            total_units = len(prs.slides)
            for s_idx, slide in enumerate(prs.slides):
                slide_texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        t = shape.text_frame.text.strip()
                        if t:
                            slide_texts.append(t)
                    if shape.has_table:
                        tbl_rows = []
                        for row in shape.table.rows:
                            tbl_rows.append(" | ".join([cell.text.strip() for cell in row.cells]))
                        if tbl_rows:
                            slide_texts.append("Table:\n" + "\n".join(tbl_rows))
                
                # Capture Speaker Notes tagged separately
                try:
                    if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                        notes_text = slide.notes_slide.notes_text_frame.text.strip()
                        if notes_text:
                            slide_texts.append(f"[Speaker Notes]: {notes_text}")
                except Exception:
                    pass

                slide_combined = "\n\n".join(slide_texts)
                if slide_combined.strip():
                    pages.append(Document(
                        page_content=slide_combined,
                        metadata={
                            "source_file": file_name,
                            "content_type": "presentation_slide",
                            "page": s_idx,
                            "page_label": s_idx + 1,
                            "unit_kind": "slide",
                            "unit_name": "slides"
                        }
                    ))

        # 📈 3. Excel Spreadsheets & CSV (.xlsx, .xls, .csv)
        elif ext in [".xlsx", ".xls", ".csv"]:
            import pandas as pd
            if ext == ".csv":
                df = pd.read_csv(file_path)
                csv_summary = f"CSV File: {file_name}\nRows: {len(df)}, Columns: {list(df.columns)}\n\n"
                rows_repr = []
                for _, row in df.iterrows():
                    rows_repr.append("; ".join([f"{col}: {val}" for col, val in row.items()]))
                csv_summary += "\n".join(rows_repr[:200])
                pages.append(Document(
                    page_content=csv_summary,
                    metadata={
                        "source_file": file_name,
                        "content_type": "spreadsheet_data",
                        "page": 0,
                        "page_label": 1,
                        "unit_kind": "sheet",
                        "unit_name": "sheets"
                    }
                ))
            else:
                xls = pd.ExcelFile(file_path)
                total_units = len(xls.sheet_names)
                for s_idx, sheet_name in enumerate(xls.sheet_names):
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    sheet_summary = f"Sheet: {sheet_name} ({len(df)} rows, Columns: {list(df.columns)})\n\n"
                    rows_repr = []
                    for _, row in df.iterrows():
                        rows_repr.append("; ".join([f"{col}: {val}" for col, val in row.items()]))
                    sheet_summary += "\n".join(rows_repr[:200])
                    pages.append(Document(
                        page_content=sheet_summary,
                        metadata={
                            "source_file": file_name,
                            "content_type": "spreadsheet_sheet",
                            "page": s_idx,
                            "page_label": s_idx + 1,
                            "sheet_name": sheet_name,
                            "unit_kind": "sheet",
                            "unit_name": "sheets"
                        }
                    ))

        # 📝 4. Text & Markdown (.txt, .md)
        elif ext in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
            pages.append(Document(
                page_content=raw_text,
                metadata={"source_file": file_name, "content_type": "text_document", "page": 0, "page_label": 1}
            ))

        # 🧠 Semantic Text Splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            separators=["\n\n# ", "\n\n## ", "\n\n### ", "\n\n", "\n• ", "\n- ", "\n1. ", ". ", "\n", " "]
        )
        
        chunks = splitter.split_documents(pages) if pages else []
        for idx, chunk in enumerate(chunks):
            chunk.page_content = re.sub(r' +', ' ', chunk.page_content).strip()
            if idx == 0 and (chunk.metadata.get("page", 0) == 0 or chunk.metadata.get("page_label", 1) == 1):
                chunk.metadata["is_header"] = True
                chunk.metadata.setdefault("section_heading", "DOCUMENT_HEADER")
            else:
                chunk.metadata.setdefault("section_heading", "GENERAL")


        if not chunks:
            chunks = [Document(
                page_content=f"Document '{file_name}' loaded successfully ({total_units} units).",
                metadata={"source_file": file_name, "content_type": "summary_placeholder", "page": 0, "page_label": 1, "is_header": True}
            )]

        return chunks, max(total_units, len(pages))

    @staticmethod
    def generate_identity_card(chunks: List[Document], file_name: str, total_units: int, ext: str = None, api_key: str = None) -> Dict[str, Any]:
        """
        Generates a rich Document Identity Card containing title, document_type, domain,
        one_line_purpose, structure_outline, key_entities, sample_questions, and provenance.
        Works reliably offline with domain heuristics, and enhances with LLM if available.
        """
        if not ext:
            ext = os.path.splitext(file_name)[1].lower()

        full_sample_text = "\n".join([c.page_content for c in chunks[:5]])
        lower_sample = full_sample_text.lower()
        first_chunk_text = chunks[0].page_content if chunks else ""
        first_lines = [line.strip() for line in first_chunk_text.split("\n") if len(line.strip()) > 3]

        # 1. 🏷️ Title Extraction
        raw_title = os.path.splitext(file_name)[0].replace("_", " ").replace("-", " ").title()
        candidate_titles = []
        for line in first_lines[:5]:
            clean_l = re.sub(r'^[#*•\-\d\.\s]+', '', line).strip()
            if 4 < len(clean_l) < 100 and not any(k in clean_l.lower() for k in ["page", "drawing no", "rev:", "date:", "author:", "http", "www", "copyright"]):
                candidate_titles.append(clean_l)
        
        extracted_title = candidate_titles[0] if candidate_titles else raw_title

        # 2. 📚 Document Type & Domain Classification
        doc_type = "Technical Document"
        domain = "General"
        
        # Heuristics based on content signals
        if ext in [".xlsx", ".xls", ".csv"] or "spreadsheet_data" in lower_sample or "sheet:" in lower_sample:
            doc_type = "Structured Spreadsheet / Tabular Dataset"
            domain = "Data Analytics & Business"
        elif ext in [".pptx", ".ppt"] or "presentation_slide" in lower_sample:
            doc_type = "Presentation Slide Deck"
            domain = "Business & Strategy"
        elif any(k in lower_sample for k in ["single line diagram", "substation", "switchgear", "transformer", "circuit breaker", "busbar", "kv ", "drawing no", "132kv", "33kv", "11kv", "sld"]):
            doc_type = "Engineering Drawing / Single-Line Diagram (SLD)"
            domain = "Electrical Engineering & Power Systems"
        elif any(k in lower_sample for k in ["water quality index", "wqi", "environmental", "bod", "cod", "turbidity", "ph value", "water sample"]):
            doc_type = "Academic Research Paper / Technical Project Report"
            domain = "Environmental Engineering & Machine Learning"
        elif any(k in lower_sample for k in ["curriculum vitae", "resume", "work experience", "education", "technical skills", "projects", "employment history"]) and ext in [".pdf", ".docx", ".doc"]:
            doc_type = "Curriculum Vitae / Professional Resume"
            domain = "Professional Portfolio"
        elif any(k in lower_sample for k in ["abstract", "introduction", "methodology", "literature review", "references", "case study", "proposed system", "conclusion"]):
            doc_type = "Academic Research Paper / Thesis Report"
            domain = "Scientific Research & Computer Science"
        elif any(k in lower_sample for k in ["financial report", "balance sheet", "income statement", "revenue", "ebitda", "fiscal year"]):
            doc_type = "Financial Report & Statement"
            domain = "Finance & Accounting"

        # 3. 🎯 One-Line Purpose Synthesis
        if "Single-Line Diagram" in doc_type or "Electrical" in domain:
            purpose = f"This engineering document specifies the electrical architecture, substation layouts, voltage levels, and equipment protection schemes for {extracted_title}."
        elif "Environmental" in domain or "water quality" in lower_sample:
            purpose = f"This research report presents the design and implementation of computational models and Python programs to predict and analyze the Water Quality Index (WQI) for environmental monitoring."
        elif "Resume" in doc_type or "Portfolio" in domain:
            purpose = f"This professional profile summarizes career achievements, core technical competencies, educational qualifications, and project portfolios."
        elif "Spreadsheet" in doc_type:
            purpose = f"This structured dataset provides tabular records, numerical attributes, and statistical data columns for analysis."
        elif "Presentation" in doc_type:
            purpose = f"This presentation deck communicates strategic insights, project milestones, and thematic overviews across {total_units} units."
        else:
            purpose = f"This document provides in-depth technical documentation, analytical findings, and reference data regarding {extracted_title}."

        # 4. 🗂️ Structure Outline Extraction
        headings = []
        for chunk in chunks:
            for line in chunk.page_content.split("\n"):
                line_str = line.strip()
                if line_str.startswith(("#", "##", "###", "Chapter", "Section", "Sheet:", "Slide ")) or re.match(r'^\d+\.\s+[A-Z]', line_str):
                    clean_h = re.sub(r'^[#*\s]+', '', line_str).strip()
                    if clean_h and clean_h not in headings and len(clean_h) < 70:
                        headings.append(clean_h)
                if len(headings) >= 8:
                    break
            if len(headings) >= 8:
                break
        
        if not headings:
            headings = ["Introduction / Overview", "Core Technical Specifications", "System Architecture / Data", "Summary & Conclusions"]

        # 5. 🔑 Key Entities & Domain Terminology Extraction
        entity_pattern = r'\b[A-Z][a-zA-Z0-9_\-]{2,}\b'
        all_matches = re.findall(entity_pattern, full_sample_text)
        stopwords_common = {"The", "This", "That", "With", "From", "Have", "Page", "Unit", "Table", "Figure", "Each", "Some", "When", "What", "Where", "Which"}
        freq_map = {}
        for m in all_matches:
            if m not in stopwords_common and len(m) > 2:
                freq_map[m] = freq_map.get(m, 0) + 1
        
        sorted_entities = sorted(freq_map.keys(), key=lambda k: freq_map[k], reverse=True)
        key_entities = sorted_entities[:12] if sorted_entities else [extracted_title, domain]

        # 6. 💡 Contextual Sample Questions
        if "Electrical" in domain or "Single-Line Diagram" in doc_type:
            sample_questions = [
                "What are the main substation transformer ratings and voltage levels?",
                "Which circuit breakers and protection schemes are specified?",
                "Summarize the single-line diagram layout and legend details."
            ]
        elif "Environmental" in domain or "water quality" in lower_sample:
            sample_questions = [
                "What machine learning algorithms and Python models are used to predict WQI?",
                "What water quality parameters (pH, Turbidity, BOD, etc.) were evaluated?",
                "What were the case study results and prediction accuracy findings?"
            ]
        elif "Resume" in doc_type:
            sample_questions = [
                "What are the candidate's core technical skills and programming languages?",
                "Summarize their educational background and degrees.",
                "What key software projects and work experience are highlighted?"
            ]
        elif "Spreadsheet" in doc_type:
            sample_questions = [
                "What are the main columns and statistical metrics in this dataset?",
                "Compare the highest and lowest values in the table.",
                "Summarize the key data trends shown in the spreadsheet."
            ]
        else:
            sample_questions = [
                f"What is the main objective and purpose of {extracted_title}?",
                "Summarize the key findings and technical specifications in this document.",
                "What are the primary conclusions and recommendations?"
            ]

        # 7. 📦 Document Identity Card Record
        identity_card = {
            "title": extracted_title,
            "filename": file_name,
            "document_type": doc_type,
            "doc_type": doc_type,
            "domain": domain,
            "purpose": purpose,
            "one_line_purpose": purpose,
            "total_pages": total_units,
            "structure_outline": headings,
            "key_entities": key_entities,
            "sample_questions": sample_questions,
            "provenance": {
                "file_name": file_name,
                "file_extension": ext,
                "unit_count": total_units,
                "total_chunks": len(chunks)
            }
        }

        return identity_card
