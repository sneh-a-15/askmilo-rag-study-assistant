# === debug_pinecone.py ===
from pinecone import Pinecone
from dotenv import load_dotenv
import os
from sentence_transformers import SentenceTransformer

load_dotenv()

# Initialize
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)
embedder = SentenceTransformer("all-MiniLM-L6-v2")

print("=" * 60)
print("🔍 PINECONE INDEX DIAGNOSTICS")
print("=" * 60)

# 1. Check index stats
print("\n📊 Index Statistics:")
stats = index.describe_index_stats()
print(f"Total vectors: {stats.total_vector_count}")
print(f"Dimension: {stats.dimension}")
print(f"\nNamespaces:")
for namespace, data in stats.namespaces.items():
    print(f"  - {namespace}: {data.vector_count} vectors")

# 2. Test query with a sample question
print("\n" + "=" * 60)
print("🧪 TESTING QUERY")
print("=" * 60)

test_question = "What is TCP?"
test_subject = "cn"  # Computer Networks

print(f"\nQuestion: {test_question}")
print(f"Subject: {test_subject}")

# Generate embedding
vector = embedder.encode(test_question, normalize_embeddings=True).tolist()
print(f"\nEmbedding dimension: {len(vector)}")
print(f"First 5 values: {vector[:5]}")

# Query Pinecone
print(f"\n🔎 Querying namespace '{test_subject}'...")
response = index.query(
    vector=vector,
    top_k=5,
    namespace=test_subject,
    include_metadata=True
)

print(f"\n✅ Found {len(response.matches)} matches")
print("\nTop Results:")
print("-" * 60)

for i, match in enumerate(response.matches, 1):
    print(f"\n{i}. Score: {match.score:.4f}")
    print(f"   ID: {match.id}")
    if match.metadata:
        text = match.metadata.get('text', 'No text')[:200]
        print(f"   Text: {text}...")
    else:
        print("   No metadata found!")

# 3. Check if namespace exists
print("\n" + "=" * 60)
print("🔍 NAMESPACE CHECK")
print("=" * 60)

available_namespaces = list(stats.namespaces.keys())
print(f"\nAvailable namespaces: {available_namespaces}")
print(f"Looking for: {test_subject}")

if test_subject in available_namespaces:
    print(f"✅ Namespace '{test_subject}' exists")
else:
    print(f"❌ Namespace '{test_subject}' NOT FOUND!")
    print("\nAvailable options:")
    for ns in available_namespaces:
        print(f"  - {ns}")

# 4. Test with different subjects
print("\n" + "=" * 60)
print("🧪 TESTING ALL SUBJECTS")
print("=" * 60)

test_subjects = ["cn", "os", "dbms"]
test_question = "explain the basic concepts"

for subj in test_subjects:
    print(f"\n📚 Testing {subj}...")
    vector = embedder.encode(test_question, normalize_embeddings=True).tolist()
    
    try:
        response = index.query(
            vector=vector,
            top_k=3,
            namespace=subj,
            include_metadata=True
        )
        print(f"   ✅ Found {len(response.matches)} matches")
        if response.matches:
            print(f"   Best score: {response.matches[0].score:.4f}")
        else:
            print(f"   ⚠️  No matches returned")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("🎯 RECOMMENDATIONS")
print("=" * 60)

if stats.total_vector_count == 0:
    print("\n❌ Your index is EMPTY!")
    print("\n📝 You need to:")
    print("   1. Prepare your study materials (PDF/text files)")
    print("   2. Create an ingestion script to upload data to Pinecone")
    print("   3. Use the correct namespaces: CN, OS, DBMS")
elif test_subject not in available_namespaces:
    print(f"\n❌ Namespace '{test_subject}' doesn't exist!")
    print(f"\n📝 Available namespaces: {', '.join(available_namespaces)}")
    print("   Update your frontend to use these namespaces")
elif not response.matches or response.matches[0].score < 0.5:
    print("\n⚠️  Low similarity scores detected!")
    print("\n📝 Possible issues:")
    print("   1. Data quality: Check if uploaded content is relevant")
    print("   2. Embedding model mismatch: Ensure same model for upload/query")
    print("   3. Chunking: Data might be split poorly")
else:
    print("\n✅ Everything looks good!")
    print("   Check your answer_question() function logic")

print("\n" + "=" * 60)