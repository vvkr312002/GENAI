import os
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel, RunnableLambda
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

app = FastAPI(title="YouTube Video QA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is missing. Add it to your environment or a .env file.")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

template = PromptTemplate(
    template="""
You are a helpful assistant.

Answer only from the provided transcript context.
If the context is insufficient, say: "I don't know based on this video's transcript."

Keep the answer clear and direct.
If relevant, mention the most useful timestamp from the context.

Context:
{context}

Question:
{question}

Answer:
""",
    input_variables=["context", "question"],
)

parser = StrOutputParser()

video_cache: Dict[str, dict] = {}


class VideoRequest(BaseModel):
    video_id: str


class AskRequest(BaseModel):
    video_id: str
    question: str


def seconds_to_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def fetch_transcript_chunks(video_id: str):
    api = YouTubeTranscriptApi()

    try:
        fetched_transcript = api.fetch(video_id, languages=["en"])
    except NoTranscriptFound:
        fetched_transcript = api.fetch(video_id)

    transcript_chunks = []
    for chunk in fetched_transcript:
        transcript_chunks.append({
            "text": chunk.text,
            "start": getattr(chunk, "start", 0),
            "duration": getattr(chunk, "duration", 0),
        })

    return transcript_chunks


def format_docs(retrieved_docs):
    formatted_parts = []
    for doc in retrieved_docs:
        timestamp = seconds_to_timestamp(doc.metadata.get("start", 0))
        formatted_parts.append(f"[{timestamp}] {doc.page_content}")
    return "\n\n".join(formatted_parts)


def build_chain(transcript_chunks):
    texts = [chunk["text"] for chunk in transcript_chunks]
    metadatas = [{"start": chunk["start"], "duration": chunk["duration"]} for chunk in transcript_chunks]

    docs = splitter.create_documents(texts, metadatas=metadatas)

    vector_store = FAISS.from_documents(docs, embeddings)
    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 6})

    parallel_chain = RunnableParallel({
        "context": retriever | RunnableLambda(format_docs),
        "question": RunnablePassthrough()
    })

    main_chain = parallel_chain | template | llm | parser
    return vector_store, retriever, main_chain


def get_or_create_video_objects(video_id: str):
    if video_id in video_cache:
        return video_cache[video_id]

    transcript_chunks = fetch_transcript_chunks(video_id)
    vector_store, retriever, main_chain = build_chain(transcript_chunks)

    video_cache[video_id] = {
        "transcript_chunks": transcript_chunks,
        "vector_store": vector_store,
        "retriever": retriever,
        "chain": main_chain,
    }
    return video_cache[video_id]


@app.get("/")
def root():
    return {"message": "YouTube Video QA API is running."}


@app.post("/index_video")
def index_video(req: VideoRequest):
    try:
        get_or_create_video_objects(req.video_id)
        return {"message": "Current video loaded successfully. You can now ask questions."}
    except TranscriptsDisabled:
        raise HTTPException(status_code=400, detail="Transcripts are disabled for this video.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask")
def ask(req: AskRequest):
    try:
        objects = get_or_create_video_objects(req.video_id)
        answer = objects["chain"].invoke(req.question)
        return {"answer": answer}
    except TranscriptsDisabled:
        raise HTTPException(status_code=400, detail="Transcripts are disabled for this video.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))