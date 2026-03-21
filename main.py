# === main.py ===
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from contextlib import asynccontextmanager
from collections import defaultdict
import time
import uvicorn

from rag_utils import answer_question, generate_followups, warmup_cache, cleanup_executor

# --- Rate limiting config ---
RATE_LIMIT_REQUESTS = 10   # max requests per window
RATE_LIMIT_WINDOW = 60     # window in seconds

# In-memory store: { ip: [timestamp, timestamp, ...] }
request_counts: dict = defaultdict(list)


def is_rate_limited(ip: str) -> bool:
    """Return True if the IP has exceeded the rate limit."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Keep only timestamps within the current window
    request_counts[ip] = [t for t in request_counts[ip] if t > window_start]

    if len(request_counts[ip]) >= RATE_LIMIT_REQUESTS:
        return True

    request_counts[ip].append(now)
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events"""
    print("🚀 Starting up...")
    await warmup_cache()
    print("✅ Application ready!")

    yield

    print("🛑 Shutting down...")
    cleanup_executor()
    print("✅ Cleanup complete")


app = FastAPI(title="AskMilo API", lifespan=lifespan)

# --- CORS fix: no wildcard with credentials ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models with validation ---
class QuestionRequest(BaseModel):
    question: str
    subject: str = "CN"
    answer: str = ""

    @field_validator("question")
    @classmethod
    def question_must_be_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        if len(v) > 500:
            raise ValueError("Question too long. Keep it under 500 characters.")
        return v

    @field_validator("subject")
    @classmethod
    def subject_must_be_valid(cls, v):
        allowed = {"CN", "OS", "DBMS"}
        if v.upper() not in allowed:
            raise ValueError(f"Subject must be one of: {', '.join(allowed)}")
        return v.upper()


class AnswerResponse(BaseModel):
    answer: str
    rag_used: bool
    sources: int


class FollowupResponse(BaseModel):
    followups: str


# --- Routes ---
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
async def ask_question_route(request: QuestionRequest, req: Request):
    ip = req.client.host
    if is_rate_limited(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again."
        )

    try:
        result = await answer_question(
            subject=request.subject,
            question=request.question
        )
        return result
    except Exception as e:
        print(f"Error in /api/ask: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@app.post("/api/followup", response_model=FollowupResponse)
async def get_followups(request: QuestionRequest, req: Request):
    ip = req.client.host
    if is_rate_limited(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again."
        )

    try:
        followups = await generate_followups(
            subject=request.subject,
            question=request.question,
            answer=request.answer  # add this
        )
        return {"followups": followups}
    except Exception as e:
        print(f"Error in /api/followup: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )