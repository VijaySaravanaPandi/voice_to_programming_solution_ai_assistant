"""
Tool Execution Module
Executes actions based on classified intent.
All file operations are restricted to the /output/ directory.
Supports compound commands, chat memory context, and graceful degradation.
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from intent import llm_chat

# ─────────────────────────────────────────────
# Output directory (safe zone)
# ─────────────────────────────────────────────

def get_output_dir() -> Path:
    """Returns the designated output directory (creates it if needed)"""
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def safe_path(filename: str) -> Path:
    """
    Returns a safe path within the output directory.
    Sanitizes the filename to prevent path traversal.
    """
    output_dir = get_output_dir()
    # Strip any path separators — filenames only
    safe_name = Path(filename).name
    # Remove dangerous characters
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', safe_name)
    if not safe_name or safe_name.startswith('.'):
        safe_name = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return output_dir / safe_name


# ─────────────────────────────────────────────
# Main dispatcher
# ─────────────────────────────────────────────

async def execute_tool(
    intent_data: Dict[str, Any],
    original_text: str,
    chat_memory: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """
    Dispatch to the appropriate tool based on intent.
    Supports compound commands — when is_compound=True, executes all listed intents.
    Returns a dict with action, output, and files_created.
    """
    intent = intent_data.get("intent", "general_chat")
    if chat_memory is None:
        chat_memory = []

    handlers = {
        "create_file": _handle_create_file,
        "write_code":  _handle_write_code,
        "summarize":   _handle_summarize,
        "general_chat": lambda id, t: _handle_chat(id, t, chat_memory),
    }

    # ── Primary intent execution ──
    handler = handlers.get(intent, lambda id, t: _handle_chat(id, t, chat_memory))
    try:
        result = await handler(intent_data, original_text)
    except Exception as e:
        # Graceful degradation: tool failed, return error without crashing
        result = {
            "action": f"Tool execution failed for intent '{intent}'",
            "output": f"⚠️ An error occurred while executing the '{intent}' action:\n\n`{str(e)}`\n\nPlease try again or rephrase your command.",
            "files_created": [],
        }

    # ── Compound commands — execute additional intents ──
    if intent_data.get("is_compound") and intent_data.get("compound_intents"):
        compound_outputs = [result.get("output", "")]
        compound_files = list(result.get("files_created", []))
        compound_actions = [result.get("action", "")]

        for compound_intent in intent_data["compound_intents"]:
            if compound_intent == intent:
                continue  # skip primary (already done)

            sub_handler = handlers.get(compound_intent, lambda id, t: _handle_chat(id, t, chat_memory))
            sub_intent_data = {**intent_data, "intent": compound_intent}

            # For compound summarize+save, pass the primary output as context
            if compound_intent == "create_file" and intent == "summarize":
                sub_intent_data["_summary_content"] = result.get("output", "")

            try:
                sub_result = await sub_handler(sub_intent_data, original_text)
                compound_outputs.append(sub_result.get("output", ""))
                compound_files.extend(sub_result.get("files_created", []))
                compound_actions.append(sub_result.get("action", ""))
            except Exception as e:
                compound_outputs.append(f"⚠️ Sub-action '{compound_intent}' failed: {str(e)}")

        result["output"] = "\n\n---\n\n".join(o for o in compound_outputs if o)
        result["files_created"] = compound_files
        result["action"] = " + ".join(a for a in compound_actions if a)

    return result


# ─────────────────────────────────────────────
# Tool Handlers
# ─────────────────────────────────────────────

async def _handle_create_file(intent_data: Dict, text: str) -> Dict[str, Any]:
    """Create a new file (empty or with basic content)"""
    filename = intent_data.get("filename")

    if not filename:
        # Generate a filename based on content hint
        hint = intent_data.get("content_hint", "file")
        words = re.sub(r'[^\w\s]', '', hint).split()[:3]
        filename = "_".join(w.lower() for w in words) + ".txt" if words else "new_file.txt"

    file_path = safe_path(filename)

    # If file already exists, add timestamp suffix
    if file_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        ts = datetime.now().strftime("%H%M%S")
        file_path = safe_path(f"{stem}_{ts}{suffix}")

    # Check if there's summary content to write (compound summarize+save)
    summary_content = intent_data.get("_summary_content", "")
    if summary_content:
        content = f"# Summary\nGenerated: {datetime.now().isoformat()}\nOriginal request: {text[:100]}\n\n{summary_content}"
    else:
        content = f"# Created by Voice AI Agent\n# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n# Request: {text[:100]}\n"

    file_path.write_text(content, encoding="utf-8")

    return {
        "action": f"Created file: {file_path.name}",
        "output": f"✅ File **{file_path.name}** created successfully in the output folder.\n\nPath: `output/{file_path.name}`",
        "files_created": [str(file_path.relative_to(get_output_dir()))],
    }


async def _handle_write_code(intent_data: Dict, text: str) -> Dict[str, Any]:
    """Generate code using LLM and write it to a file"""
    language = intent_data.get("language", "python")
    filename = intent_data.get("filename")
    content_hint = intent_data.get("content_hint", text)

    if not filename:
        ext_map = {
            "python": ".py", "javascript": ".js", "typescript": ".ts",
            "java": ".java", "cpp": ".cpp", "c": ".c", "go": ".go",
            "rust": ".rs", "html": ".html", "css": ".css", "bash": ".sh",
        }
        ext = ext_map.get((language or "python").lower(), ".py")
        words = re.sub(r'[^\w\s]', '', content_hint).split()[:3]
        base = "_".join(w.lower() for w in words) if words else "generated_code"
        filename = f"{base}{ext}"

    file_path = safe_path(filename)

    # Generate code via LLM
    code_prompt = f"""Write {language} code for the following request:
"{text}"

Rules:
1. Write ONLY the code — no explanation, no markdown fences
2. Include helpful inline comments
3. Make it production-quality and complete
4. The code should be self-contained and runnable"""

    code_system = f"You are an expert {language} developer. Output ONLY clean, commented code without any markdown formatting or explanation."

    try:
        generated_code = await llm_chat(code_prompt, system=code_system)
    except Exception as e:
        return {
            "action": "Code generation failed",
            "output": f"⚠️ Could not generate code: {str(e)}\n\nPlease ensure your LLM (Ollama or Groq) is configured and running.",
            "files_created": [],
        }

    # Strip any markdown fences that slipped through
    generated_code = re.sub(r'^```\w*\n?', '', generated_code, flags=re.MULTILINE)
    generated_code = re.sub(r'\n?```$', '', generated_code, flags=re.MULTILINE)
    generated_code = generated_code.strip()

    if not generated_code:
        return {
            "action": "Code generation produced empty output",
            "output": "⚠️ The LLM returned empty code. Please rephrase your request.",
            "files_created": [],
        }

    # Write to file
    file_path.write_text(generated_code, encoding="utf-8")

    preview = generated_code[:500] + ("..." if len(generated_code) > 500 else "")

    return {
        "action": f"Generated {language} code → {file_path.name}",
        "output": f"✅ Code written to **{file_path.name}**\n\n```{language}\n{preview}\n```",
        "files_created": [str(file_path.relative_to(get_output_dir()))],
    }


async def _handle_summarize(intent_data: Dict, text: str) -> Dict[str, Any]:
    """Summarize provided text content"""
    content_hint = intent_data.get("content_hint", "")
    filename = intent_data.get("filename")

    # Extract text to summarize (remove the "summarize" instruction itself)
    text_to_summarize = content_hint if content_hint and len(content_hint) > 20 else text

    # Try to strip the meta-instruction from the text
    patterns = [
        r'(?:summarize|summarise|give me a summary of|tldr)[:\s]+(.+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            # Only use if not including the "save to" part
            candidate = re.sub(r'\s+and\s+save\s+(?:it\s+)?to\s+\S+.*$', '', candidate, flags=re.IGNORECASE).strip()
            if len(candidate) > 10:
                text_to_summarize = candidate
                break

    if len(text_to_summarize.strip()) < 15:
        return {
            "action": "Summarization skipped",
            "output": "⚠️ Not enough text to summarize. Please provide the text content after 'summarize:'",
            "files_created": [],
        }

    summary_prompt = f"""Summarize the following text concisely but comprehensively:

"{text_to_summarize}"

Provide:
1. A 2-3 sentence summary
2. Key points (bullet list)
3. Main takeaway"""

    try:
        summary = await llm_chat(summary_prompt)
    except Exception as e:
        return {
            "action": "Summarization failed",
            "output": f"⚠️ Could not summarize: {str(e)}",
            "files_created": [],
        }

    files_created = []

    # Save to file if explicitly requested (compound command or filename provided)
    if filename and not intent_data.get("_skip_file_save"):
        save_filename = filename
        file_path = safe_path(save_filename)
        file_content = f"# Summary\nGenerated: {datetime.now().isoformat()}\nOriginal request: {text[:100]}\n\n{summary}"
        file_path.write_text(file_content, encoding="utf-8")
        files_created.append(str(file_path.relative_to(get_output_dir())))
        action = f"Summarized text → saved to {file_path.name}"
    else:
        action = "Summarized text"

    return {
        "action": action,
        "output": f"📝 **Summary:**\n\n{summary}",
        "files_created": files_created,
    }


async def _handle_chat(intent_data: Dict, text: str, chat_memory: List[dict]) -> Dict[str, Any]:
    """Handle general chat / Q&A with persistent memory context"""
    system = """You are a helpful, friendly AI assistant embedded in a voice-controlled agent.
Answer questions concisely and helpfully. Format your responses using markdown when appropriate.
You have memory of the current session's conversation history."""

    # Build context-aware prompt using session memory
    if chat_memory:
        # Include recent conversation turns for context
        context_lines = []
        for msg in chat_memory[-6:]:  # last 3 exchanges
            role = "User" if msg["role"] == "user" else "Assistant"
            context_lines.append(f"{role}: {msg['content'][:200]}")

        context = "\n".join(context_lines)
        full_prompt = f"Previous conversation context:\n{context}\n\nCurrent user message: {text}"
    else:
        full_prompt = text

    try:
        response = await llm_chat(full_prompt, system=system)
    except Exception as e:
        return {
            "action": "General chat (LLM unavailable)",
            "output": f"⚠️ Could not reach the LLM: {str(e)}\n\nPlease ensure Ollama is running (`ollama serve`) or set your GROQ_API_KEY.",
            "files_created": [],
        }

    return {
        "action": "General chat response",
        "output": f"💬 {response}",
        "files_created": [],
    }
