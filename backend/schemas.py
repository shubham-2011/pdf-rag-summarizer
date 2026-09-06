from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class UploadResponse(BaseModel):
    filename: str
    document_id: str
    total_pages: Optional[int] = 0
    total_chunks: int
    message: str
    unit_count: Optional[int] = None
    unit_name: Optional[str] = "pages"
    format: Optional[str] = "pdf"
    details: Optional[str] = None

class SummarizeRequest(BaseModel):
    document_id: str = Field(..., description="Document collection ID")
    model_name: Optional[str] = "gpt-4o-mini"
    api_key: Optional[str] = None

class SummarizeResponse(BaseModel):
    filename: str
    summary_and_roadmap: str

class ChatQueryRequest(BaseModel):
    document_id: Optional[str] = Field(None, description="Single document collection ID")
    document_ids: Optional[List[str]] = Field(None, description="Multi-document workspace collection IDs")
    question: str = Field(..., description="User query")
    model_name: Optional[str] = "gpt-4o-mini"
    api_key: Optional[str] = None
    enable_web_search: Optional[bool] = False
    chat_history: Optional[List[Dict[str, str]]] = Field(None, description="Past chat conversation history")

class SourceCitation(BaseModel):
    page: Any
    file: str
    section: Optional[str] = None
    snippet: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None

    def __init__(self, **data: Any):
        if "text" in data and ("snippet" not in data or data["snippet"] is None):
            data["snippet"] = data["text"]
        elif "snippet" in data and ("text" not in data or data["text"] is None):
            data["text"] = data["snippet"]
        if "snippet" not in data:
            data["snippet"] = ""
        if "text" not in data:
            data["text"] = ""
        super().__init__(**data)

class ChatQueryResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    served_by: Optional[str] = "unknown"
    finish_reason: Optional[str] = "stop"
    latency_ms: Optional[float] = 0.0

