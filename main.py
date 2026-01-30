# === main.py ===
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn

# Import your RAG utilities
from rag_utils import answer_question, generate_followups, warmup_cache, save_cache, cleanup_executor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events"""
    # Startup
    print("🚀 Starting up...")
    await warmup_cache()
    print("✅ Application ready!")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    save_cache()
    cleanup_executor()
    print("✅ Cleanup complete")


# Initialize FastAPI app with lifespan
app = FastAPI(title="AskMilo API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    subject: str = "CN"


class AnswerResponse(BaseModel):
    answer: str
    rag_used: bool
    sources: int


class FollowupResponse(BaseModel):
    followups: str


@app.get("/")
async def root():
    return {
        "message": "AskMilo API is running",
        "endpoints": {
            "/api/ask": "POST - Ask a question",
            "/api/followup": "POST - Generate follow-up questions"
        }
    }


@app.post("/api/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """Answer a question using RAG"""
    try:
        result = await answer_question(
            subject=request.subject,
            question=request.question
        )
        return result
    except Exception as e:
        print(f"Error in /api/ask: {e}")
        return {
            "answer": "An error occurred. Please try again.",
            "rag_used": False,
            "sources": 0
        }


@app.post("/api/followup", response_model=FollowupResponse)
async def get_followups(request: QuestionRequest):
    """Generate follow-up questions"""
    try:
        followups = await generate_followups(
            subject=request.subject,
            question=request.question
        )
        return {"followups": followups}
    except Exception as e:
        print(f"Error in /api/followup: {e}")
        return {
            "followups": "1. What are the key concepts?\n2. How is this applied in practice?"
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )