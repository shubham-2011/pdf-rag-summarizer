import os
import re
import fitz
from typing import List, Tuple
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from services.image_service import ImageService
import config

class PDFService:
    """PDF parsing, PyMuPDF block layout preservation, human-centric semantic chunking, and audit validation service."""
    
    @staticmethod
    def audit_pdf(pdf_path: str, file_size: int) -> Tuple[bool, str]:
        """Audits PDF file against size, encryption, page count, and text/image extractability constraints."""
        if file_size == 0:
            return False, "Uploaded PDF file is empty (0 bytes)."
            
        if file_size > config.MAX_FILE_SIZE_BYTES:
            size_mb = round(file_size / (1024 * 1024), 2)
            return False, f"PDF file size ({size_mb} MB) exceeds maximum allowed limit of {config.MAX_FILE_SIZE_MB} MB."
            
        try:
            with open(pdf_path, "rb") as f:
                header = f.read(10)
            if not header.startswith(b"%PDF"):
                return False, "Corrupted or invalid PDF structure: Missing %PDF file header."
            reader = PdfReader(pdf_path)
            doc_fitz = fitz.open(pdf_path)
        except Exception as e:
            return False, f"Corrupted or invalid PDF structure: {str(e)}"
            
        if reader.is_encrypted:
            return False, "PDF is password-protected or encrypted. Please remove password protection before uploading."
            
        total_pages = len(reader.pages)
        if total_pages == 0:
            return False, "PDF contains 0 pages."
            
        if total_pages > config.MAX_PAGE_COUNT:
            return False, f"Document contains {total_pages} pages, which exceeds maximum limit of {config.MAX_PAGE_COUNT} pages."
            
        total_extracted_text = ""
        total_images = 0
        for i, page in enumerate(reader.pages[:5]):
            text = page.extract_text() or ""
            total_extracted_text += text.strip()
            if i < len(doc_fitz):
                total_images += len(doc_fitz[i].get_images())

        if len(total_extracted_text) < config.MIN_TEXT_CHARS:
            return False, "PDF contains no extractable text. It appears to be a scanned image-only document; OCR is not supported yet."
            
        return True, "PDF audit passed successfully."

    @staticmethod
    def process_pdf(pdf_path: str, api_key: str = None) -> Tuple[List[Document], int]:
        """Parses PDF text using PyMuPDF block layout preservation and extracts embedded images/figures for vector indexing."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found at {pdf_path}")
            
        doc_fitz = fitz.open(pdf_path)
        total_pages = len(doc_fitz)
        file_name = os.path.basename(pdf_path)
        
        pages = []
        section_headers = ["TECHNICAL SKILLS", "ACADEMIC PROJECTS", "PROJECTS", "EXPERIENCE", "EDUCATION", "TRAINING", "CAREER OBJECTIVE", "CERTIFICATIONS"]
        
        # 📐 Block Layout Extraction: Preserves tables, multi-column sections, and logical paragraph blocks
        for page_idx in range(total_pages):
            page_fitz = doc_fitz[page_idx]
            blocks = page_fitz.get_text("blocks")
            
            # Sort blocks vertically (y0) then horizontally (x0)
            blocks.sort(key=lambda b: (b[1], b[0]))
            
            page_text_blocks = []
            for b in blocks:
                block_text = b[4].strip()
                if len(block_text) > 5:
                    page_text_blocks.append(block_text)
                    
            page_combined_text = "\n\n".join(page_text_blocks)
            
            if page_combined_text.strip():
                doc_obj = Document(
                    page_content=page_combined_text,
                    metadata={
                        "source_file": file_name,
                        "content_type": "text_chunk",
                        "page": page_idx,
                        "page_label": page_idx + 1
                    }
                )
                pages.append(doc_obj)

        # 🧠 Human-Centric Semantic Splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            separators=[
                "\n\nTECHNICAL SKILLS", "\n\nACADEMIC PROJECTS", "\n\nPROJECTS", "\n\nEXPERIENCE", "\n\nEDUCATION", "\n\nTRAINING",
                "\n\n# ", "\n\n## ", "\n\n### ",
                "\n\n\n", "\n\n", 
                "\n• ", "\n- ", "\n* ", "\n➢ ", "\n1. ", "\n2. ", "\n3. ",
                ". ", "? ", "! ",
                "\n", " "
            ]
        )
        
        text_chunks = splitter.split_documents(pages)
        
        for chunk in text_chunks:
            chunk.page_content = re.sub(r' +', ' ', chunk.page_content).strip()
            active_sec = "GENERAL"
            content_upper = chunk.page_content.upper()
            for header in section_headers:
                if header in content_upper:
                    active_sec = header
                    break
            chunk.metadata["section_heading"] = active_sec
        
        # 🖼️ Extract and Caption Embedded Images / Diagrams
        image_chunks = ImageService.extract_and_caption_images(pdf_path, api_key=api_key)
        
        all_chunks = text_chunks + image_chunks
        return all_chunks, total_pages
