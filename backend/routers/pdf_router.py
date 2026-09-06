import os
import shutil
import uuid
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from schemas import UploadResponse, SummarizeRequest, SummarizeResponse
from services.pdf_service import PDFService
from services.vector_service import VectorService
from services.summarizer_service import SummarizerService
from services.ingest_adapter import IngestAdapter, IngestAdapterError
import config

router = APIRouter(prefix="/api/pdf", tags=["PDF Processing"])

document_cache = {}

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None)
):
    is_pdf = file.filename.lower().endswith(".pdf")
    if not is_pdf and not getattr(config, "MULTIFORMAT_ENABLED", False):
        raise HTTPException(
            status_code=400,
            detail="PDF Cannot Be Embedded: Only PDF files are supported."
        )
        
    doc_id = str(uuid.uuid4())[:8]
    temp_path = os.path.join(config.TEMP_UPLOAD_DIR, f"{doc_id}_{file.filename}")
    converted_pdf_path = None
    
    try:
        # Save temp file to perform audit / conversion
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        from services.metadata_service import MetadataService
        from services.document_service import DocumentService

        raw_format = IngestAdapter.detect_format(temp_path)
        file_size = os.path.getsize(temp_path)
        key = api_key or config.OPENAI_API_KEY
        
        is_converted = False
        unit_source = None
        orig_format = raw_format
        para_count = 0
        table_count = 0

        # Non-PDF formats: attempt high-fidelity conversion if enabled
        if raw_format != "pdf" and getattr(config, "MULTIFORMAT_ENABLED", False):
            try:
                conv_res = IngestAdapter.to_pdf(temp_path, allow_fallback=True)
                if conv_res.was_converted and conv_res.pdf_path:
                    converted_pdf_path = conv_res.pdf_path
                    is_converted = True
                    unit_source = conv_res.unit_source
            except Exception:
                pass

        # Format-specific auditing and container extraction
        if raw_format == "pdf" or is_converted:
            effective_path = converted_pdf_path if is_converted else temp_path
            effective_size = os.path.getsize(effective_path)

            # Mandatory Pre-Embedding PDF Audit
            is_valid, audit_reason = PDFService.audit_pdf(effective_path, effective_size)
            if not is_valid:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                if converted_pdf_path and os.path.exists(converted_pdf_path):
                    os.remove(converted_pdf_path)
                raise HTTPException(status_code=400, detail=f"PDF Cannot Be Embedded: {audit_reason}")

            chunks, total_units = PDFService.process_pdf(effective_path, api_key=key)
            unit_kind = "page"
            unit_name = "pages"
            unit_count = total_units
            unit_source = unit_source or "native-pdf"
            details = f"{total_units} Pages (rendered via {unit_source})" if is_converted else f"{total_units} Pages"
            total_pages = total_units

        elif raw_format == "doc":
            # Legacy binary .doc format requires an external converter
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise HTTPException(
                status_code=400,
                detail="Document Cannot Be Embedded: Legacy binary .doc format requires an external converter (LibreOffice or MS Word), which is not available in this environment. Please convert to .docx or .pdf."
            )

        elif raw_format == "docx":
            # Pre-audit DOCX size and readability
            if file_size > config.MAX_FILE_SIZE_BYTES:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise HTTPException(status_code=400, detail=f"Document Cannot Be Embedded: File size exceeds {config.MAX_FILE_SIZE_MB}MB limit.")

            # Native multi-container extraction (paragraphs, tables, headers, footers, textboxes)
            chunks, total_units = DocumentService.process_document(temp_path, api_key=key)
            
            # Count paragraphs and tables from chunks metadata
            if chunks and hasattr(chunks[0], "metadata"):
                para_count = chunks[0].metadata.get("paragraph_count", len(chunks))
                table_count = chunks[0].metadata.get("table_count", 0)

            unit_kind = "paragraph"
            unit_name = "paragraphs"
            unit_count = None  # Crucial: DOCX has no fixed page count
            unit_source = "native-ast"
            details = f"{para_count} paragraphs, {table_count} tables"
            total_pages = 0

        elif raw_format in ["pptx", "ppt"]:
            chunks, total_units = DocumentService.process_document(temp_path, api_key=key)
            unit_kind = "slide"
            unit_name = "slides"
            unit_count = total_units
            unit_source = "native-ast"
            details = f"{total_units} Slides"
            total_pages = 0

        elif raw_format in ["xlsx", "xls", "csv"]:
            chunks, total_units = DocumentService.process_document(temp_path, api_key=key)
            unit_kind = "sheet"
            unit_name = "sheets"
            unit_count = total_units
            unit_source = "native-ast"
            details = f"{total_units} Sheets"
            total_pages = 0

        else:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise HTTPException(status_code=400, detail=f"Document format '{raw_format.upper()}' is not supported.")

        # Persist local vector collection with manifest recording real format and units
        VectorService.create_collection(
            chunks,
            collection_name=doc_id,
            api_key=key,
            unit_count=unit_count,
            unit_kind=unit_kind,
            filename=file.filename,
            format_ext=raw_format,
            unit_source=unit_source,
            is_converted=is_converted,
            original_format=orig_format
        )
        
        # Register in Authoritative Metadata Registry (SQLite)
        with open(temp_path, "rb") as pf:
            content_hash = MetadataService.calculate_file_hash(pf.read())

        MetadataService.register_document(
            doc_id=doc_id,
            content_hash=content_hash,
            filename=file.filename,
            format_ext=raw_format,
            mime_type="application/pdf" if (raw_format == "pdf" or is_converted) else f"application/{raw_format}",
            size_bytes=file_size,
            unit_count=unit_count,
            unit_kind=unit_kind,
            storage_path=temp_path,
            status="READY",
            unit_source=unit_source,
            is_converted=is_converted,
            original_format=orig_format,
            paragraph_count=para_count,
            table_count=table_count
        )

        collection_dir = os.path.join(config.VECTOR_STORE_DIR, doc_id)
        MetadataService.update_status(doc_id, "READY", index_path=collection_dir)

        # Generate and save Document Identity Card and Outlines
        identity_card = DocumentService.generate_identity_card(chunks, file.filename, unit_count or 1, ext=f".{raw_format}", api_key=key)
        MetadataService.save_identity(doc_id, identity_card)

        outline_entries = []
        for idx, heading in enumerate(identity_card.get("structure_outline", [])):
            outline_entries.append({
                "locator_kind": unit_kind,
                "locator_index": 1,
                "locator_label": "1",
                "heading": heading,
                "level": 1,
                "char_count": 100
            })
        if outline_entries:
            MetadataService.save_outline(doc_id, outline_entries)
        
        document_cache[doc_id] = {
            "filename": file.filename,
            "temp_path": temp_path,
            "chunks": chunks,
            "total_pages": total_pages,
            "unit_count": unit_count,
            "unit_kind": unit_kind,
            "format": raw_format,
            "unit_source": unit_source,
            "is_converted": is_converted
        }
        
        return UploadResponse(
            filename=file.filename,
            document_id=doc_id,
            total_pages=total_pages,
            total_chunks=len(chunks),
            message=f"{raw_format.upper()} audit passed, all containers extracted, and vector embedding completed successfully.",
            unit_count=unit_count,
            unit_name=unit_name,
            format=raw_format,
            details=details
        )
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if converted_pdf_path and os.path.exists(converted_pdf_path):
            os.remove(converted_pdf_path)
        raise HTTPException(status_code=500, detail=f"Document Cannot Be Embedded: {str(e)}")


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_pdf(req: SummarizeRequest):
    doc_data = document_cache.get(req.document_id)
    if not doc_data:
        raise HTTPException(status_code=404, detail="Document ID not found. Please upload the PDF first.")
        
    key = req.api_key or config.OPENAI_API_KEY
    try:
        summary_text = SummarizerService.generate_summary(
            chunks=doc_data["chunks"],
            api_key=key,
            model_name=req.model_name
        )
        return SummarizeResponse(
            filename=doc_data["filename"],
            summary_and_roadmap=summary_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to summarize document: {str(e)}")
