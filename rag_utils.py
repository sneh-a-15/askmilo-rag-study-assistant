# === rag_utils.py (PRODUCTION VERSION) ===
from pinecone import Pinecone
from dotenv import load_dotenv
import os
import asyncio
import time
from typing import List, Dict, Optional
import hashlib
import json
from groq import Groq
from sentence_transformers import SentenceTransformer
import signal
import sys

load_dotenv()

# Environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Init
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

# ✅ CRITICAL: Use same embedding model as ingestion
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Cache setup
CACHE_FILE = "embedding_cache.json"
embedding_cache = {}

# Executor for thread pool
executor = None

# Namespace mapping cache
available_namespaces = {}

def get_executor():
    """Get or create thread pool executor"""
    global executor
    if executor is None:
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=4)
    return executor

def cleanup_executor():
    """Cleanup thread pool on shutdown"""
    global executor
    if executor is not None:
        executor.shutdown(wait=False)
        executor = None

def load_cache():
    """Load embedding cache from file"""
    global embedding_cache
    try:
        with open(CACHE_FILE, 'r') as f:
            embedding_cache = json.load(f)
        print(f"📦 Loaded {len(embedding_cache)} cached embeddings")
    except (FileNotFoundError, json.JSONDecodeError):
        embedding_cache = {}
        print("📦 Starting with empty cache")

def save_cache():
    """Save embedding cache to file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(embedding_cache, f)
    except Exception as e:
        print(f"Failed to save cache: {e}")

def get_embedding_hash(text: str) -> str:
    """Create consistent hash for caching"""
    return hashlib.md5(text.encode()).hexdigest()

def refresh_namespaces():
    """Refresh available namespaces from Pinecone"""
    global available_namespaces
    try:
        stats = index.describe_index_stats()
        # Map uppercase to actual namespace (case-insensitive lookup)
        available_namespaces = {
            ns.upper(): ns for ns in stats.namespaces.keys()
        }
        print(f"📚 Available namespaces: {list(stats.namespaces.keys())}")
    except Exception as e:
        print(f"⚠️  Failed to refresh namespaces: {e}")
        available_namespaces = {}

def normalize_namespace(subject: str) -> str:
    """
    Normalize namespace to match what's actually in Pinecone
    Handles case-insensitive matching: CN -> cn
    """
    # Refresh namespaces if cache is empty
    if not available_namespaces:
        refresh_namespaces()
    
    # Try to find matching namespace (case-insensitive)
    subject_upper = subject.upper()
    
    if subject_upper in available_namespaces:
        actual_namespace = available_namespaces[subject_upper]
        if actual_namespace != subject:
            print(f"🔄 Normalized '{subject}' → '{actual_namespace}'")
        return actual_namespace
    
    # If not found, return lowercase version (common case)
    print(f"⚠️  Namespace '{subject}' not in cache, trying lowercase")
    return subject.lower()

def get_embedding_fast(text) -> List[float]:
    """
    Generate embedding with caching
    ✅ CRITICAL: Must use same model as data ingestion
    """
    # Normalize input
    if isinstance(text, list):
        text = " ".join(map(str, text))
    else:
        text = str(text)

    text_hash = get_embedding_hash(text)

    # Return cached embedding if available
    if text_hash in embedding_cache:
        return embedding_cache[text_hash]

    try:
        # Generate embedding with normalization
        embedding = embedder.encode(
            text,
            normalize_embeddings=True  # ✅ Important for cosine similarity
        ).tolist()

        # Cache the result
        embedding_cache[text_hash] = embedding

        # Periodically save cache
        if len(embedding_cache) % 10 == 0:
            save_cache()

        return embedding

    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        return [0.0] * 384

def select_best_context(matches, max_chunks=3, min_score=0.5):
    """
    Select relevant chunks
    ✅ Adjusted threshold based on your actual scores (0.65-0.69)
    """
    print(f"\n🔍 Analyzing {len(matches)} matches:")
    for i, m in enumerate(matches[:5]):
        print(f"  {i+1}. Score: {m.score:.4f} | ID: {m.id}")
    
    # Filter by minimum score
    good_matches = [m for m in matches if m.score >= min_score]
    
    if not good_matches:
        # Fall back to top matches even if below threshold
        print(f"⚠️  No matches above {min_score}, using top {max_chunks}")
        good_matches = matches[:max_chunks]
    else:
        print(f"✅ Found {len(good_matches)} matches above {min_score}")
    
    return good_matches[:max_chunks]

async def answer_question(subject: str, question: str, top_k: int = 5) -> Dict:
    """
    Answer question using RAG with Pinecone + Groq
    Only answers questions relevant to the selected subject
    """
    start_time = time.time()
    
    try:
        # ✅ Normalize namespace (CN -> cn)
        actual_namespace = normalize_namespace(subject)
        
        print(f"\n{'='*60}")
        print(f"📝 Question: {question}")
        print(f"📚 Subject: {subject} → {actual_namespace}")
        print(f"{'='*60}")
        
        # Generate embedding
        vector = get_embedding_fast(question)
        embed_time = time.time() - start_time
        print(f"⏱️  Embedding: {embed_time:.3f}s")
        
        # Query Pinecone
        query_start = time.time()
        response = index.query(
            vector=vector,
            top_k=top_k,
            namespace=actual_namespace,
            include_metadata=True
        )
        query_time = time.time() - query_start
        print(f"⏱️  Query: {query_time:.3f}s")
        print(f"📊 Retrieved: {len(response.matches)} matches")
        
        # Check if we got results
        if not response.matches:
            print("❌ No matches returned!")
            refresh_namespaces()
            available = list(available_namespaces.values())
            
            return {
                "answer": f"No data found for '{subject}'. Available subjects: {', '.join(available)}.",
                "rag_used": False,
                "sources": 0
            }
        
        # Check if scores are too low (question not relevant to subject)
        best_score = response.matches[0].score if response.matches else 0
        if best_score < 0.4:
            subject_names = {
                'cn': 'Computer Networks',
                'os': 'Operating Systems', 
                'dbms': 'Database Management'
            }
            subject_name = subject_names.get(actual_namespace, actual_namespace.upper())
            
            print(f"⚠️  Low relevance score: {best_score:.3f}")
            return {
                "answer": f"This question doesn't seem related to {subject_name}. Please select the correct subject or rephrase your question.",
                "rag_used": False,
                "sources": 0
            }
        
        # Select best context
        best_matches = select_best_context(response.matches, max_chunks=3, min_score=0.5)
        
        # Extract text from metadata
        contexts = []
        for match in best_matches:
            if match.metadata and "text" in match.metadata:
                contexts.append(match.metadata["text"])
            else:
                print(f"⚠️  Match {match.id} missing 'text' in metadata")
        
        if not contexts:
            print("❌ No text content in matches!")
            return {
                "answer": "Found documents but no readable content. Check data format in Pinecone.",
                "rag_used": False,
                "sources": 0
            }
        
        print(f"✅ Using {len(contexts)} context chunks")
        
        # Prepare context
        context_block = "\n\n---\n\n".join(contexts)
        if len(context_block) > 4000:
            context_block = context_block[:4000] + "..."
        
        print(f"📄 Context: {len(context_block)} chars")
        
        # Subject names
        subject_names = {
            'cn': 'Computer Networks',
            'os': 'Operating Systems',
            'dbms': 'Database Management Systems'
        }
        subject_full = subject_names.get(actual_namespace, actual_namespace.upper())
        
        # ✅ IMPROVED: Better prompt for clean, well-formatted answers
        llm_start = time.time()
        prompt = f"""You are Milo, a helpful {subject_full} tutor.

Reference Material:
{context_block}

Student's Question: {question}

Instructions:
- Provide a clear, well-structured answer
- Use short paragraphs (2-3 sentences each)
- Use simple language
- If listing items, use natural language (e.g., "There are three types: X, Y, and Z")
- No markdown formatting (no bold, no headers, no bullet points)
- Keep it concise (3-4 paragraphs maximum)
- Only answer if the question relates to {subject_full}

Answer:"""
        
        def call_groq():
            return groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,  # Slightly higher for more natural language
                max_tokens=600,   # Reduced to keep answers concise
            )
        
        loop = asyncio.get_event_loop()
        completion = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), call_groq),
            timeout=30.0
        )
        
        llm_time = time.time() - llm_start
        answer_text = completion.choices[0].message.content.strip()
        
        # ✅ POST-PROCESS: Clean up the answer
        answer_text = clean_answer_formatting(answer_text)
        
        print(f"⏱️  LLM: {llm_time:.3f}s")
        print(f"⏱️  Total: {time.time() - start_time:.3f}s")
        print(f"✅ Answer: {len(answer_text)} chars")

        return {
            "answer": answer_text,
            "rag_used": True,
            "sources": len(contexts)
        }
    
    except asyncio.TimeoutError:
        print("❌ Timeout!")
        return {
            "answer": "Request timeout. Please try again.",
            "rag_used": False,
            "sources": 0
        }
    except asyncio.CancelledError:
        print("❌ Cancelled")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "answer": "An error occurred. Please try again.",
            "rag_used": False,
            "sources": 0
        }


def clean_answer_formatting(text: str) -> str:
    """
    Clean up answer formatting for better readability
    Removes markdown, fixes spacing, formats paragraphs
    """
    import re
    
    # Remove markdown bold (**text** or __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # Remove markdown headers (# Header)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    
    # Remove bullet points and convert to natural text
    text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
    
    # Remove excessive newlines (more than 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Ensure proper paragraph spacing
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    text = '\n\n'.join(paragraphs)
    
    return text

async def generate_followups(subject: str, question: str) -> str:
    """Generate SHORT, SIMPLE follow-up questions"""
    
    try:
        prompt = f"""Generate 2 brief follow-up questions for a student asking: "{question}"

Rules:
- Maximum 8 words each
- Simple and direct
- No explanations
- {subject} related

Examples:
1. What are its main advantages?
2. How does it compare to alternatives?

Your questions:
1.
2."""

        def call_groq():
            return groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=60,
            )

        loop = asyncio.get_event_loop()
        completion = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), call_groq),
            timeout=15.0
        )

        raw = completion.choices[0].message.content.strip()
        
        # Clean and shorten questions
        lines = [l.strip() for l in raw.split('\n') if l.strip()]
        questions = []
        
        for line in lines:
            # Remove numbering
            clean = line.lstrip('0123456789.- ').strip()
            if len(clean) > 5:
                # Truncate if too long
                words = clean.split()
                if len(words) > 8:
                    clean = ' '.join(words[:8])
                if not clean.endswith('?'):
                    clean += '?'
                questions.append(clean)
        
        # Return first 2
        if len(questions) >= 2:
            return f"1. {questions[0]}\n2. {questions[1]}"
        elif len(questions) == 1:
            return f"1. {questions[0]}\n2. How does it work?"
        else:
            return "1. What are the key concepts?\n2. How is it used?"
    
    except Exception as e:
        print(f"Followup error: {e}")
        return "1. What are the key points?\n2. How is it applied?"
    
async def warmup_cache():
    """Preload common queries and namespaces"""
    print("🔥 Warming up...")
    
    # Load namespaces
    refresh_namespaces()
    
    # Cache common embeddings
    for query in [
        "what is tcp",
        "explain deadlock",
        "what is normalization",
        "how does dns work",
        "explain process scheduling"
    ]:
        get_embedding_fast(query)

    save_cache()
    print("✅ Ready!")


def shutdown_handler(signum, frame):
    """Handle shutdown gracefully"""
    print("\n🛑 Shutting down...")
    save_cache()
    cleanup_executor()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# Initialize
load_cache()