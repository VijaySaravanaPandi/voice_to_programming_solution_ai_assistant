# 🎙️ VoiceAgent AI — Voice-Controlled Local AI Agent

A full-stack voice-controlled AI agent that transcribes speech, classifies intent, executes local tools, and displays the entire pipeline in a premium web UI.

![Pipeline: Audio → STT → Intent → Tool → Output](https://img.shields.io/badge/Pipeline-Audio→STT→Intent→Tool→Output-6366f1?style=for-the-badge)

![Status: Ready to Run](https://img.shields.io/badge/Status-Ready_to_Run-success?style=flat-square)
![Tests: Passing](https://img.shields.io/badge/Version-1.0.0-blue?style=flat-square)

---

### ✅ Deployment Status
Both the **FastAPI Backend** and **Vanilla JS Frontend** are fully integrated and verified. The backend serves the frontend assets directly, ensuring smooth communication and zero CORS issues when running on the default `localhost:8000`.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Browser)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │Microphone│  │  Upload  │  │    Text Input        │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
└───────┼──────────────┼───────────────────┼──────────────┘
        │              │                   │
        └──────────────▼───────────────────┘
                       │  HTTP POST /api/process
                       ▼
┌──────────────────────────────────────────────────────────┐
│                   FastAPI Backend                         │
│                                                           │
│  ┌─────────────┐    ┌───────────────────┐                │
│  │  STT Module │    │  Intent Classifier│                │
│  │ Groq Whisper│───▶│  Ollama / Groq LLM│                │
│  └─────────────┘    └────────┬──────────┘                │
│                               │                           │
│                     ┌─────────▼──────────┐               │
│                     │   Tool Executor    │               │
│                     │ create_file        │               │
│                     │ write_code         │               │
│                     │ summarize          │               │
│                     │ general_chat       │               │
│                     └─────────┬──────────┘               │
│                               │                           │
│                     ┌─────────▼──────────┐               │
│                     │   output/ folder   │  ← Safe zone  │
│                     └────────────────────┘               │
└──────────────────────────────────────────────────────────┘
```

---

## ✨ Features

| Feature | Details |
|---|---|
| **Audio Input** | Browser mic recording + file upload (WAV/MP3/M4A/OGG/FLAC) |
| **Speech-to-Text** | Groq Whisper large-v3 (fast, accurate, API-based) |
| **Intent Classification** | Ollama (local) with Groq fallback + rule-based last resort |
| **Supported Intents** | Create File · Write Code · Summarize · General Chat |
| **Compound Commands** | e.g. "Summarize this and save it to summary.txt" |
| **Human-in-the-Loop** | Confirmation dialog before any file operation |
| **File Safety** | All file ops restricted to `output/` folder |
| **Output Browser** | View/browse all generated files in the UI |
| **Session History** | Persistent in-session history with click-to-replay |
| **Graceful Errors** | All pipeline failures shown with clear messages |

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/intern-1-project.git
cd intern-1-project
```

### 2. Install Python dependencies
```bash
pip install -r backend/requirements.txt
```

### 3. Configure API keys
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```
Get a **free** Groq API key at [console.groq.com](https://console.groq.com)

### 4. (Optional) Start Ollama for local LLM
```bash
# Install Ollama: https://ollama.ai
ollama pull gemma3:4b
```
> If Ollama is not running, the system automatically falls back to Groq LLM.

### 5. Start the backend
Go into the backend folder and start the server:
```bash
cd backend
python main.py
```

### 6. Open the UI (Automatic)
In a **new terminal**, run the dev script from the project root. This will print the dashboard and automatically open your browser:
```bash
python dev.py
```
*Note: You can also manually visit **http://localhost:8000**.*

---

## 📁 Project Structure

```
intern-1-project/
├── backend/
│   ├── main.py          # FastAPI server + all API routes
│   ├── stt.py           # Speech-to-Text (Groq Whisper)
│   ├── intent.py        # Intent classification (Ollama/Groq/rule-based)
│   ├── tools.py         # Tool execution (file, code, summarize, chat)
│   └── requirements.txt
├── frontend/
│   ├── index.html       # Single-page UI
│   ├── style.css        # Dark glassmorphism design
│   └── app.js           # Full client-side logic
├── output/              # ⚠️  All agent-created files go here ONLY
├── check_setup.py       # Pre-flight setup checker
├── .env.example         # Environment variable template
└── README.md
```

---

## 🧠 Model Choices & Hardware Notes

### Speech-to-Text: Groq Whisper large-v3
**Why Groq API instead of local Whisper?**
- Running `openai/whisper-large-v3` locally requires ~6GB VRAM (GPU) or is very slow on CPU (30–60s per 10s audio).
- Groq's inference hardware runs Whisper at **~200x realtime** with a free tier.
- The Groq API is free for reasonable usage and has no cold-start latency.
- For a local-only variant, replace `stt.py` with `faster-whisper` or `whisper.cpp`.

### LLM: Ollama (llama3) → Groq fallback
- **Primary**: Ollama with `llama3` runs locally with no API calls. Requires 8 GB RAM minimum.
- **Fallback**: If Ollama is not installed/running, the system uses `llama3-8b-8192` via Groq API automatically.
- **Last resort**: A rule-based keyword classifier if both LLMs are unavailable.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve frontend UI |
| `GET` | `/api/health` | Backend health check |
| `POST` | `/api/process` | Process audio file (multipart) |
| `POST` | `/api/text` | Process text input (JSON) |
| `GET` | `/api/history` | Get session history |
| `DELETE` | `/api/history` | Clear session history |
| `GET` | `/api/files` | List output files |
| `GET` | `/api/files/{filename}` | Get file content |

---

## 🎯 Example Commands

| You say | Intent | Action |
|---|---|---|
| "Create a Python file with a retry function" | `write_code` | Generates retry.py in output/ |
| "Make a new text file called notes.txt" | `create_file` | Creates notes.txt in output/ |
| "Summarize this: [text]" | `summarize` | Returns formatted summary |
| "What is machine learning?" | `general_chat` | LLM answer in UI |
| "Summarize this and save it to summary.txt" | `summarize` + `create_file` | Compound: summarizes AND saves |

---

## 🛡️ Safety

- **All file creation is restricted to the `output/` directory** — path traversal attacks are blocked.
- Filenames are sanitized before writing.
- A human-in-the-loop confirmation dialog appears before any file operation.

---

## 📋 Requirements

- Python 3.9+
- Groq API key (free at [console.groq.com](https://console.groq.com))
- Ollama (optional, for local LLM)
- Modern browser (Chrome/Edge/Firefox) for mic access

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
