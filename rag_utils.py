# === rag_utils.py (PRODUCTION VERSION) ===
from pinecone import Pinecone
from dotenv import load_dotenv
from fastembed import TextEmbedding
import os
import asyncio
import time
from typing import List, Dict
from groq import Groq
import signal
import sys

load_dotenv()

# === ENV ===
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# === INIT ===
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Load embedding model once at startup
print("Loading embedding model...")
embedding_model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
print("Embedding model ready")

# === EXECUTOR ===
executor = None

# === NAMESPACE CACHE ===
available_namespaces = {}


def get_executor():
    global executor
    if executor is None:
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=4)
    return executor


def cleanup_executor():
    global executor
    if executor is not None:
        executor.shutdown(wait=False)
        executor = None


def refresh_namespaces():
    global available_namespaces
    try:
        stats = index.describe_index_stats()
        available_namespaces = {
            ns.upper(): ns for ns in stats.namespaces.keys()
        }
        print(f"Available namespaces: {list(stats.namespaces.keys())}")
    except Exception as e:
        print(f"Failed to refresh namespaces: {e}")
        available_namespaces = {}


def normalize_namespace(subject: str) -> str:
    if not available_namespaces:
        refresh_namespaces()

    subject_upper = subject.upper()

    if subject_upper in available_namespaces:
        actual_namespace = available_namespaces[subject_upper]
        if actual_namespace != subject:
            print(f"Normalized '{subject}' → '{actual_namespace}'")
        return actual_namespace

    print(f"Namespace '{subject}' not in cache, trying lowercase")
    return subject.lower()


def get_embedding_fast(text) -> List[float]:
    """Generate embedding using fastembed (ONNX MiniLM, no torch needed)."""
    if isinstance(text, list):
        text = " ".join(map(str, text))
    else:
        text = str(text)

    try:
        embeddings = list(embedding_model.embed([text]))
        return embeddings[0].tolist()
    except Exception as e:
        print(f"Embedding failed: {e}")
        return [0.0] * 384


def select_best_context(matches, max_chunks=3, min_score=0.5):
    print(f"\n🔍 Analyzing {len(matches)} matches:")
    for i, m in enumerate(matches[:5]):
        print(f"  {i+1}. Score: {m.score:.4f} | ID: {m.id}")

    good_matches = [m for m in matches if m.score >= min_score]

    if not good_matches:
        print(f"No matches above {min_score}, using top {max_chunks}")
        good_matches = matches[:max_chunks]
    else:
        print(f"Found {len(good_matches)} matches above {min_score}")

    return good_matches[:max_chunks]


async def answer_question(subject: str, question: str, top_k: int = 5) -> Dict:
    start_time = time.time()

    try:
        actual_namespace = normalize_namespace(subject)

        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"Subject: {subject} → {actual_namespace}")
        print(f"{'='*60}")

        # Generate embedding
        vector = get_embedding_fast(question)
        embed_time = time.time() - start_time
        print(f"Embedding: {embed_time:.3f}s")

        # Query Pinecone
        query_start = time.time()
        response = index.query(
            vector=vector,
            top_k=top_k,
            namespace=actual_namespace,
            include_metadata=True
        )
        query_time = time.time() - query_start
        print(f"Query: {query_time:.3f}s")
        print(f"Retrieved: {len(response.matches)} matches")

        if not response.matches:
            print("No matches returned!")
            refresh_namespaces()
            available = list(available_namespaces.values())
            return {
                "answer": f"No data found for '{subject}'. Available subjects: {', '.join(available)}.",
                "rag_used": False,
                "sources": 0
            }

        best_score = response.matches[0].score if response.matches else 0
        if best_score < 0.4:
            subject_names = {
                'cn': 'Computer Networks',
                'os': 'Operating Systems',
                'dbms': 'Database Management'
            }
            subject_name = subject_names.get(actual_namespace, actual_namespace.upper())
            print(f"Low relevance score: {best_score:.3f}")
            return {
                "answer": f"This question doesn't seem related to {subject_name}. Please select the correct subject or rephrase your question.",
                "rag_used": False,
                "sources": 0
            }

        best_matches = select_best_context(response.matches, max_chunks=3, min_score=0.5)

        contexts = []
        for match in best_matches:
            if match.metadata and "text" in match.metadata:
                contexts.append(match.metadata["text"])
            else:
                print(f"Match {match.id} missing 'text' in metadata")

        if not contexts:
            print("No text content in matches!")
            return {
                "answer": "Found documents but no readable content. Check data format in Pinecone.",
                "rag_used": False,
                "sources": 0
            }

        print(f"Using {len(contexts)} context chunks")

        context_block = "\n\n---\n\n".join(contexts)
        if len(context_block) > 4000:
            context_block = context_block[:4000] + "..."

        print(f"Context: {len(context_block)} chars")

        subject_names = {
            'cn': 'Computer Networks',
            'os': 'Operating Systems',
            'dbms': 'Database Management Systems'
        }
        subject_full = subject_names.get(actual_namespace, actual_namespace.upper())

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
                temperature=0.5,
                max_tokens=600,
            )

        loop = asyncio.get_running_loop()
        completion = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), call_groq),
            timeout=30.0
        )

        llm_time = time.time() - llm_start
        answer_text = completion.choices[0].message.content.strip()
        answer_text = clean_answer_formatting(answer_text)

        print(f"LLM: {llm_time:.3f}s")
        print(f"Total: {time.time() - start_time:.3f}s")
        print(f"Answer: {len(answer_text)} chars")

        return {
            "answer": answer_text,
            "rag_used": True,
            "sources": len(contexts)
        }

    except asyncio.TimeoutError:
        print("Timeout!")
        return {
            "answer": "Request timeout. Please try again.",
            "rag_used": False,
            "sources": 0
        }
    except asyncio.CancelledError:
        print("Cancelled")
        raise
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "answer": "An error occurred. Please try again.",
            "rag_used": False,
            "sources": 0
        }


def clean_answer_formatting(text: str) -> str:
    import re

    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    text = '\n\n'.join(paragraphs)

    return text


async def generate_followups(subject: str, question: str, answer: str = "") -> str:
    try:
        prompt = f"""A student asked: "{question}"

They received this answer:
{answer}

Generate 2 natural follow-up questions a curious student would actually ask next.

Rules:
- Each question should be complete and meaningful
- 10-15 words maximum
- Directly related to the answer given
- No explanations, just the questions
- {subject} related

Your questions:
1.
2."""

        def call_groq():
            return groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=80,  # slightly more room
            )

        loop = asyncio.get_running_loop()
        completion = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), call_groq),
            timeout=15.0
        )

        raw = completion.choices[0].message.content.strip()

        lines = [l.strip() for l in raw.split('\n') if l.strip()]
        questions = []

        for line in lines:
            clean = line.lstrip('0123456789.- ').strip()
            if len(clean) > 5:
                if not clean.endswith('?'):
                    clean += '?'
                questions.append(clean)

        if len(questions) >= 2:
            return f"1. {questions[0]}\n2. {questions[1]}"
        elif len(questions) == 1:
            return f"1. {questions[0]}\n2. How does it work in practice?"
        else:
            return "1. What are the key concepts?\n2. How is it used in real systems?"

    except Exception as e:
        print(f"Followup error: {e}")
        return "1. What are the key points?\n2. How is it applied in practice?"

async def warmup_cache():
    print("Warming up...")
    refresh_namespaces()
    print("Ready!")


def shutdown_handler(signum, frame):
    print("\nShutting down...")
    cleanup_executor()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)