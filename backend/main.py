import os
import csv
import shutil
import tempfile
from uuid import uuid4
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from openai import BadRequestError
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from prompts import RAG_SYSTEM_PROMPT

app = FastAPI(title="Assignment 03 - The Final API Frontier")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_env_file(path: str = ".env"):
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except FileNotFoundError:
        pass


_load_env_file()

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

if not os.environ.get("GITHUB_TOKEN"):
    print("Warning: GITHUB_TOKEN is missing.")

llm = None
def _get_llm():
    global llm
    if llm is None:
        api_key = os.environ.get("GITHUB_TOKEN")
        if not api_key:
            raise RuntimeError("GITHUB_TOKEN is missing.")
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            base_url="https://models.inference.ai.azure.com",
            temperature=0.1,
        )
    return llm

QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "easy_lm_docs")
TOP_K = 2

qdrant_client = None

def _get_qdrant_client():
    global qdrant_client
    if qdrant_client is None:
        QDRANT_URL = os.environ.get("QDRANT_URL")
        QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise RuntimeError("QDRANT_URL and QDRANT_API_KEY are required.")
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        VECTOR_SIZE = len(embeddings.embed_query("vector-size-probe"))
        existing_collections = qdrant_client.get_collections().collections
        if not any(collection.name == QDRANT_COLLECTION for collection in existing_collections):
            qdrant_client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
    return qdrant_client

class QueryRequest(BaseModel):
    query: str

class TextUploadRequest(BaseModel):
    text: str


def _load_csv_documents(file_path: str, source_name: str):
    with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
        sample = csv_file.read(4096)
        csv_file.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
        except csv.Error:
            dialect = csv.excel

        try:
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        except csv.Error:
            has_header = False

        documents = []
        if has_header:
            reader = csv.DictReader(csv_file, dialect=dialect)
            for row_index, row in enumerate(reader, start=1):
                row_items = [f"{key}: {value}" for key, value in row.items() if key and value not in (None, "")]
                row_text = "; ".join(row_items).strip()
                if row_text:
                    documents.append(
                        Document(
                            page_content=row_text,
                            metadata={"source": source_name, "row_number": row_index},
                        )
                    )
        else:
            reader = csv.reader(csv_file, dialect=dialect)
            for row_index, row in enumerate(reader, start=1):
                row_text = ", ".join(cell for cell in row if cell).strip()
                if row_text:
                    documents.append(
                        Document(
                            page_content=row_text,
                            metadata={"source": source_name, "row_number": row_index},
                        )
                    )

    return documents

def _index_documents(docs, source_name: str, upload_type: str):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(docs)

    if not chunks:
        return 0

    chunk_texts = [doc.page_content for doc in chunks]
    chunk_vectors = embeddings.embed_documents(chunk_texts)

    points = []
    for index, (chunk, vector) in enumerate(zip(chunks, chunk_vectors)):
        payload = {
            "text": chunk.page_content,
            "source_name": source_name,
            "upload_type": upload_type,
            "chunk_index": index,
        }

        for key, value in (chunk.metadata or {}).items():
            if isinstance(value, (str, int, float, bool)):
                payload[f"meta_{key}"] = value

        points.append(
            PointStruct(
                id=str(uuid4()),
                vector=vector,
                payload=payload,
            )
        )

    client = _get_qdrant_client()
    client.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
    return len(chunks)


def _search_qdrant(query_vector, top_k: int):
    client = _get_qdrant_client()
    response = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    return getattr(response, "points", response)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Write upload to a secure system temp file (do NOT use working dir or user-supplied name)
    tmp_file = None
    try:
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        normalized_suffix = suffix.lower()
        if normalized_suffix not in {".pdf", ".csv"}:
            raise HTTPException(status_code=400, detail="Only PDF and CSV files are supported.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            tmp_file = tf.name
            # stream copy to temp file
            shutil.copyfileobj(file.file, tf)

        # Ingestion from temp path
        if normalized_suffix == ".csv":
            docs = _load_csv_documents(tmp_file, source_name=os.path.basename(file.filename) or "uploaded.csv")
            upload_type = "csv"
        else:
            loader = PyPDFLoader(tmp_file)
            docs = loader.load()
            upload_type = "pdf"

        total_chunks = _index_documents(docs, source_name=os.path.basename(file.filename) or "uploaded.file", upload_type=upload_type)

        return {
            "message": "File ingested, chunked, embedded, and indexed.",
            "total_chunks": total_chunks,
        }
    except Exception as e:
        # Provide a clearer error to the client and log server-side
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {e}")
    finally:
        # Always attempt to clean up the temp file
        try:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)
        except Exception:
            pass


@app.post("/upload-text")
async def upload_text(payload: TextUploadRequest):
    text = payload.text.strip()
    if not text:
        return {"message": "No text provided.", "total_chunks": 0}

    docs = [Document(page_content=text, metadata={"source": "clipboard-text"})]
    total_chunks = _index_documents(docs, source_name="clipboard-text", upload_type="text")
    return {
        "message": "Text ingested, chunked, embedded, and indexed.",
        "total_chunks": total_chunks,
    }

@app.post("/query")
async def query_document(req: QueryRequest):
    # Retrieval step (top-k from Qdrant)
    query_vector = embeddings.embed_query(req.query)
    try:
        search_result = _search_qdrant(query_vector, TOP_K)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching Qdrant: {e}")

    if not search_result:
        return {"answer": "No relevant information found. Try a better question."}

    searched_chunks = []
    for result in search_result:
        payload = None
        if hasattr(result, "payload"):
            payload = result.payload
        elif isinstance(result, dict):
            payload = result.get("payload") or result

        if isinstance(payload, dict):
            text = payload.get("text")
            if text:
                searched_chunks.append(text)
        elif isinstance(payload, str) and payload.strip():
            searched_chunks.append(payload)

    if not searched_chunks:
        return {"answer": "No relevant information found. Try a better question."}
    
    # Compile the retrieved context
    context = "\n\n".join(searched_chunks)
    
    # Build the system prompt with context
    system_prompt = RAG_SYSTEM_PROMPT.format(
        instructions=f"DOCUMENT CONTEXT:\n{context}\n\nUser Query: {req.query}\n\nProvide a concise answer in 2-5 sentences."
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Query: {req.query}"
        ),
    ]

    # Generation step
    try:
        try:
            llm_instance = _get_llm()
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        response = llm_instance.invoke(messages)
    except BadRequestError as error:
        error_message = str(error)
        if "content_filter" in error_message or "ResponsibleAIPolicyViolation" in error_message:
            return {
                "answer": "The backend blocked this request.",
                "source_chunks": searched_chunks,
            }
        raise
    
    return {
        "answer": response.content.strip(),
        "source_chunks": searched_chunks
    }