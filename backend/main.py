"""
Voice-Controlled Local AI Agent - FastAPI Backend
Main entry point - handles all API routes
Bonus features: compound commands, human-in-the-loop, graceful degradation,
                memory/chat context, model benchmarking timings
"""

import os
import sys
import json
import tempfile
import uuid
import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from dotenv import load_dotenv

# Load .env from project root (works regardless of CWD)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from stt import transcribe_audio
from intent import classify_intent, llm_chat
from tools import execute_tool, get_output_dir

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────
app = FastAPI(
    title="Voice AI Agent",
    description="Local voice-controlled AI agent with intent classification and tool execution",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend directory
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ─────────────────────────────────────────────
# In-memory session storage
# ─────────────────────────────────────────────
session_history: List[dict] = []

# Chat context memory: list of {role, content} for ongoing conversation
chat_memory: List[dict] = []
MAX_CHAT_MEMORY = 10  # Keep last 10 exchanges


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/")
async def serve_ui():
    """Serve the frontend UI"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Voice AI Agent API is running. Place frontend in /frontend/index.html"}


@app.get("/style.css")
async def serve_css():
    """Serve CSS (relative path from index.html)"""
    css_path = FRONTEND_DIR / "style.css"
    if css_path.exists():
        return FileResponse(str(css_path), media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS not found")


@app.get("/app.js")
async def serve_js():
    """Serve JS (relative path from index.html)"""
    js_path = FRONTEND_DIR / "app.js"
    if js_path.exists():
        return FileResponse(str(js_path), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JS not found")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "output_dir": str(get_output_dir()),
    }


@app.post("/api/process")
async def process_audio(
    audio: UploadFile = File(...),
    confirm: Optional[str] = Form(default="true"),
):
    """
    Main pipeline endpoint:
    1. Receive audio file
    2. Transcribe via Whisper/Groq (timed)
    3. Classify intent via LLM (timed)
    4. Execute tool (timed)
    5. Return full pipeline result with benchmark timings
    """
    request_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()

    result = {
        "id": request_id,
        "timestamp": timestamp,
        "transcription": None,
        "intent": None,
        "intent_details": {},
        "action_taken": None,
        "output": None,
        "files_created": [],
        "error": None,
        "status": "processing",
        "benchmarks": {},  # Timing data for model benchmarking
    }

    try:
        # Step 1: Save uploaded audio to temp
        audio_bytes = await audio.read()
        if len(audio_bytes) == 0:
            result["error"] = "Empty audio file received. Please record or upload a valid audio file."
            result["status"] = "failed"
            session_history.append(result)
            return JSONResponse(content=result)

        # Graceful degradation: check minimum file size (< 1KB is likely silence)
        if len(audio_bytes) < 1024:
            result["error"] = "Audio file is too short or silent. Please speak clearly for at least 1 second."
            result["status"] = "failed"
            session_history.append(result)
            return JSONResponse(content=result)

        suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
        temp_dir = Path(tempfile.gettempdir())
        temp_path = temp_dir / f"voice_agent_{request_id}{suffix}"
        temp_path.write_bytes(audio_bytes)

        # Step 2: Speech-to-Text (timed)
        t0 = time.perf_counter()
        try:
            transcription = await transcribe_audio(str(temp_path))
        except Exception as stt_err:
            result["error"] = f"Speech-to-text failed: {str(stt_err)}. Please check your GROQ_API_KEY or try again."
            result["status"] = "failed"
            result["benchmarks"]["stt_ms"] = round((time.perf_counter() - t0) * 1000)
            session_history.append(result)
            return JSONResponse(content=result)

        result["benchmarks"]["stt_ms"] = round((time.perf_counter() - t0) * 1000)
        result["transcription"] = transcription

        # Graceful degradation: empty transcription
        if not transcription or transcription.strip() == "":
            result["error"] = "Could not transcribe audio — speech was unintelligible. Please speak clearly and try again."
            result["status"] = "failed"
            session_history.append(result)
            return JSONResponse(content=result)

        # Graceful degradation: too short transcription (likely noise)
        if len(transcription.strip()) < 3:
            result["error"] = f"Transcription too short: '{transcription}'. Please speak a complete command."
            result["status"] = "failed"
            session_history.append(result)
            return JSONResponse(content=result)

        # Step 3: Intent Classification (timed)
        t1 = time.perf_counter()
        try:
            intent_data = await classify_intent(transcription)
        except Exception as intent_err:
            # Graceful degradation: fall back to chat on intent failure
            intent_data = {
                "intent": "general_chat",
                "filename": None,
                "language": None,
                "content_hint": transcription,
                "is_compound": False,
                "compound_intents": [],
                "llm_used": "Rule-based fallback (LLM unavailable)",
            }
            result["error"] = f"Intent classification degraded: {str(intent_err)}"

        result["benchmarks"]["intent_ms"] = round((time.perf_counter() - t1) * 1000)
        result["intent"] = intent_data.get("intent", "general_chat")
        result["intent_details"] = intent_data

        # Step 4: Tool Execution (timed) — pass memory context for chat
        t2 = time.perf_counter()
        tool_result = await execute_tool(intent_data, transcription, chat_memory=chat_memory)
        result["benchmarks"]["tool_ms"] = round((time.perf_counter() - t2) * 1000)
        result["benchmarks"]["total_ms"] = round((time.perf_counter() - t0) * 1000)

        result["action_taken"] = tool_result.get("action")
        result["output"] = tool_result.get("output")
        result["files_created"] = tool_result.get("files_created", [])
        result["status"] = "success"

        # Update chat memory for general_chat intents
        _update_chat_memory(transcription, result["output"] or "")

        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}. Please try again."
        result["status"] = "error"

    session_history.append(result)
    return JSONResponse(content=result)


@app.post("/api/text")
async def process_text(body: dict):
    """Process text input directly (for testing without audio)"""
    request_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()
    text = body.get("text", "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    # Graceful degradation: reject very short nonsense inputs
    if len(text) < 2:
        raise HTTPException(status_code=400, detail="Input too short. Please enter a meaningful command.")

    result = {
        "id": request_id,
        "timestamp": timestamp,
        "transcription": text,
        "intent": None,
        "intent_details": {},
        "action_taken": None,
        "output": None,
        "files_created": [],
        "error": None,
        "status": "processing",
        "benchmarks": {},
    }

    try:
        # Intent Classification (timed)
        t0 = time.perf_counter()
        try:
            intent_data = await classify_intent(text)
        except Exception as intent_err:
            # Graceful degradation
            intent_data = {
                "intent": "general_chat",
                "filename": None,
                "language": None,
                "content_hint": text,
                "is_compound": False,
                "compound_intents": [],
                "llm_used": "Rule-based fallback",
            }

        result["benchmarks"]["intent_ms"] = round((time.perf_counter() - t0) * 1000)
        result["intent"] = intent_data.get("intent", "general_chat")
        result["intent_details"] = intent_data

        # Tool Execution (timed) — pass chat memory
        t1 = time.perf_counter()
        tool_result = await execute_tool(intent_data, text, chat_memory=chat_memory)
        result["benchmarks"]["tool_ms"] = round((time.perf_counter() - t1) * 1000)
        result["benchmarks"]["total_ms"] = round((time.perf_counter() - t0) * 1000)

        result["action_taken"] = tool_result.get("action")
        result["output"] = tool_result.get("output")
        result["files_created"] = tool_result.get("files_created", [])
        result["status"] = "success"

        # Update chat memory
        _update_chat_memory(text, result["output"] or "")

    except HTTPException:
        raise
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
        result["status"] = "error"

    session_history.append(result)
    return JSONResponse(content=result)


@app.get("/api/history")
async def get_history():
    """Return session history"""
    return {"history": session_history[-50:]}  # Last 50 entries


@app.delete("/api/history")
async def clear_history():
    """Clear session history and chat memory"""
    session_history.clear()
    chat_memory.clear()
    return {"message": "History and chat memory cleared"}


@app.get("/api/memory")
async def get_memory():
    """Return current chat memory context"""
    return {"memory": chat_memory, "count": len(chat_memory)}


@app.get("/api/files")
async def list_output_files():
    """List files in the output directory"""
    output_dir = get_output_dir()
    files = []
    for f in output_dir.rglob("*"):
        if f.is_file() and f.name != ".gitkeep":
            files.append({
                "name": f.name,
                "path": str(f.relative_to(output_dir)),
                "size": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
            })
    return {"files": files}


@app.get("/api/files/{filename}")
async def get_file_content(filename: str):
    """Get content of a file from output directory"""
    output_dir = get_output_dir()
    file_path = output_dir / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Security: ensure it's within output dir
    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    content = file_path.read_text(encoding="utf-8", errors="replace")
    return {"filename": filename, "content": content}


# ─────────────────────────────────────────────
# WebSocket for real-time updates
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _update_chat_memory(user_text: str, assistant_response: str):
    """Append to rolling chat memory for context-aware responses"""
    chat_memory.append({"role": "user", "content": user_text})
    chat_memory.append({"role": "assistant", "content": assistant_response[:500]})  # trim long outputs
    # Keep memory bounded
    while len(chat_memory) > MAX_CHAT_MEMORY * 2:
        chat_memory.pop(0)
        chat_memory.pop(0)


if __name__ == "__main__":
    # Ensure backend/ is in sys.path so module imports work from any CWD
    backend_dir = str(Path(__file__).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    
    # NPM-style startup message
    print("\n" + "="*50)
    print("      VOICE AI AGENT -- DEVELOPMENT SERVER")
    print(" " + "-"*48)
    print(f"  > Local:   http://localhost:8000")
    print(f"  > Output:  {get_output_dir()}")
    print(" " + "-"*48)
    print("  Press CTRL+C to stop the server")
    print("="*50 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[backend_dir],
        log_level="info",
    )
