import time
from fastapi import APIRouter, HTTPException
from schemas import ChatQueryRequest, ChatQueryResponse
from services.rag_service import RAGService

router = APIRouter(prefix="/api/chat", tags=["RAG Chat"])

@router.post("/query", response_model=ChatQueryResponse)
async def query_chat(req: ChatQueryRequest):
    try:
        start_t = time.time()
        res = RAGService.query(
            document_id=req.document_id,
            document_ids=req.document_ids,
            question=req.question,
            api_key=req.api_key,
            model_name=req.model_name,
            enable_web_search=req.enable_web_search or False,
            chat_history=req.chat_history
        )
        latency = round((time.time() - start_t) * 1000, 2)
        return ChatQueryResponse(
            answer=res.get("answer", ""),
            sources=res.get("sources", []),
            served_by=res.get("served_by", "rag_service"),
            finish_reason=res.get("finish_reason", "stop"),
            latency_ms=res.get("latency_ms", latency)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG Retrieval failed: {str(e)}")

