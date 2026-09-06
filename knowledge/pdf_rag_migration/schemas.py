from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class UploadResponse(BaseModel):
    filename: str
    document_id: str
    total_pages: int
    total_chunks: int
    message: str

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
    id: Optional[str] = None
    page: Any = "1"
    file: Optional[str] = "Document"
    text: Optional[str] = None
    snippet: Optional[str] = None
    origin: Optional[str] = "pdf"
    url: Optional[str] = None

class ChatQueryResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
