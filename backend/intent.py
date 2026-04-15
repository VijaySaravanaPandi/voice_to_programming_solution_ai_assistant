"""
Intent Classification Module
Uses Ollama (local LLM) to classify user intent from transcribed text.
Falls back to Groq LLM if Ollama is unavailable.
"""

import os
import json
import asyncio
import re
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

INTENT_SYSTEM_PROMPT = """You are an intent classifier for a voice-controlled AI agent.

Analyze the user's request and respond ONLY with a JSON object (no markdown, no explanation).

Supported intents:
- "create_file": User wants to create a new file or folder
- "write_code": User wants code written to a file
- "summarize": User wants text content summarized
- "general_chat": General question or conversation

JSON format:
{
  "intent": "<one of the above intents>",
  "filename": "<suggested filename with extension, or null>",
  "language": "<programming language if write_code, or null>",
  "content_hint": "<brief description of what to create/write/summarize>",
  "is_compound": <true if multiple actions needed>,
  "compound_intents": ["intent1", "intent2"] or []
}

Examples:
User: "Create a Python file with a retry function"
→ {"intent": "write_code", "filename": "retry.py", "language": "python", "content_hint": "retry function", "is_compound": false, "compound_intents": []}

User: "Make a new text file called notes.txt"
→ {"intent": "create_file", "filename": "notes.txt", "language": null, "content_hint": "empty notes file", "is_compound": false, "compound_intents": []}

User: "Summarize this: The quick brown fox jumps over the lazy dog"
→ {"intent": "summarize", "filename": null, "language": null, "content_hint": "The quick brown fox jumps over the lazy dog", "is_compound": false, "compound_intents": []}

User: "Summarize this text and save it to summary.txt"
→ {"intent": "summarize", "filename": "summary.txt", "language": null, "content_hint": "save summary", "is_compound": true, "compound_intents": ["summarize", "create_file"]}
"""


async def classify_intent(text: str) -> Dict[str, Any]:
    """Classify the user's intent from transcribed text"""
    
    # Try Ollama first (local, preferred)
    try:
        result = await _classify_ollama(text)
        result["llm_used"] = f"Ollama ({OLLAMA_MODEL})"
        return result
    except Exception as ollama_err:
        print(f"[Intent] Ollama failed: {ollama_err}, falling back to Groq...")
    
    # Fallback to Groq
    if GROQ_API_KEY:
        try:
            result = await _classify_groq(text)
            result["llm_used"] = f"Groq ({GROQ_MODEL})"
            return result
        except Exception as groq_err:
            print(f"[Intent] Groq failed: {groq_err}, using rule-based fallback...")
    
    # Final fallback: rule-based
    result = _rule_based_classify(text)
    result["llm_used"] = "Rule-based fallback"
    return result


async def _classify_ollama(text: str) -> Dict[str, Any]:
    """Classify intent using local Ollama"""
    import httpx
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    
    content = data["message"]["content"].strip()
    return _parse_json_response(content)


async def _classify_groq(text: str) -> Dict[str, Any]:
    """Classify intent using Groq API"""
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    loop = asyncio.get_event_loop()
    
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=256,
        ),
    )
    
    content = response.choices[0].message.content.strip()
    return _parse_json_response(content)


def _parse_json_response(content: str) -> Dict[str, Any]:
    """Parse JSON from LLM response, handling markdown code blocks"""
    # Strip markdown code fences if present
    content = re.sub(r"```(?:json)?\s*", "", content).strip()
    content = content.strip("`").strip()
    
    try:
        data = json.loads(content)
        # Ensure required fields
        data.setdefault("intent", "general_chat")
        data.setdefault("filename", None)
        data.setdefault("language", None)
        data.setdefault("content_hint", "")
        data.setdefault("is_compound", False)
        data.setdefault("compound_intents", [])
        return data
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return _rule_based_classify(content)


def _rule_based_classify(text: str) -> Dict[str, Any]:
    """Simple rule-based intent classifier as last resort fallback"""
    text_lower = text.lower()
    
    base = {
        "intent": "general_chat",
        "filename": None,
        "language": None,
        "content_hint": text[:200],
        "is_compound": False,
        "compound_intents": [],
    }
    
    # Code writing detection
    code_keywords = ["write code", "generate code", "create a python", "create a javascript",
                     "write a function", "write a script", "code for", "implement"]
    if any(kw in text_lower for kw in code_keywords):
        base["intent"] = "write_code"
        if "python" in text_lower:
            base["language"] = "python"
            base["filename"] = "generated_code.py"
        elif "javascript" in text_lower or "js" in text_lower:
            base["language"] = "javascript"
            base["filename"] = "generated_code.js"
        else:
            base["language"] = "python"
            base["filename"] = "generated_code.py"
        return base
    
    # File creation detection
    file_keywords = ["create a file", "make a file", "new file", "create file",
                     "create a folder", "make a folder"]
    if any(kw in text_lower for kw in file_keywords):
        base["intent"] = "create_file"
        # Try to extract filename
        match = re.search(r'called?\s+(\S+\.\w+)', text_lower)
        if match:
            base["filename"] = match.group(1)
        return base
    
    # Summarize detection
    if any(kw in text_lower for kw in ["summarize", "summary", "summarise", "tldr"]):
        base["intent"] = "summarize"
        return base
    
    return base


async def llm_chat(prompt: str, system: str = "") -> str:
    """
    Generic LLM call for code generation, summarization, etc.
    Returns the raw text response.
    """
    if not system:
        system = "You are a helpful AI assistant. Be concise and accurate."
    
    errors = []

    # Try Ollama first
    try:
        return await _llm_ollama(prompt, system)
    except Exception as e:
        err_msg = f"Ollama failed: {str(e)}"
        print(f"[LLM] {err_msg}")
        errors.append(err_msg)
    
    # Groq fallback
    if GROQ_API_KEY:
        try:
            return await _llm_groq(prompt, system)
        except Exception as e:
            err_msg = f"Groq fallback failed: {str(e)}"
            print(f"[LLM] {err_msg}")
            errors.append(err_msg)
    else:
        errors.append("Groq API key not configured.")
    
    # If we reached here, both failed
    detailed_error = "\n".join(errors)
    return f"Error: No LLM available.\n\nDetails:\n{detailed_error}\n\n💡 Tip: Ensure Ollama is running (`ollama serve`) or check your GROQ_API_KEY in .env"


async def _llm_ollama(prompt: str, system: str) -> str:
    import httpx
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.7},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


async def _llm_groq(prompt: str, system: str) -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2048,
        ),
    )
    return response.choices[0].message.content.strip()
