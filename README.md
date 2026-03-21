# AskMilo RAG CS Study Assistant

AskMilo is a Retrieval-Augmented Generation (RAG) project for Computer Science study topics.
It combines a FastAPI backend, Pinecone vector search, local embeddings, and a Next.js frontend.

## Features

- Ask subject-specific questions for CN, OS, and DBMS
- Retrieve relevant context from Pinecone before generating answers
- Generate short follow-up questions
- Ingest study material from PDF and TXT files into Pinecone

## Tech Stack

- Backend: FastAPI, Uvicorn
- Retrieval: Pinecone
- Embeddings: FastEmbed using sentence-transformers/all-MiniLM-L6-v2
- LLM: Groq (llama-3.1-8b-instant)
- Frontend: Next.js (App Router), React, TypeScript

## Project Structure

- Backend API and RAG logic at project root
- Frontend app inside cs-ui
- Study material inside data with per-subject folders

## Prerequisites

- Python 3.10+
- Node.js 18+
- Pinecone account and index
- Groq API key

## Environment Variables

Create a .env file in the project root:

```env
PINECONE_API_KEY=your_pinecone_api_key
INDEX_NAME=your_pinecone_index_name
GROQ_API_KEY=your_groq_api_key
```

Create a .env.local file in cs-ui:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## Installation

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd cs-ui
npm install
```

## Run Locally

Start backend:

```bash
uvicorn main:app --reload
```

Start frontend (in a new terminal):

```bash
cd cs-ui
npm run dev
```

Backend runs on http://localhost:8000 and frontend on http://localhost:3000.

## Data Ingestion

1. Put study files into:
   - data/cn
   - data/os
   - data/dbms
2. Run ingestion:

```bash
python upload.py
```

This extracts text, chunks content, generates embeddings, and upserts vectors into Pinecone namespaces.

## Embedding and Vector Details

- Embedding model: sentence-transformers/all-MiniLM-L6-v2 (via FastEmbed)
- Current vector size: 384
- Pinecone index dimension must match embedding dimension