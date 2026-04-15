import os
import requests
import logging

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_llm_response(prompt, history=""):
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{history}\n\n{prompt}",
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=20)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logging.error(e)
        return f"Graceful Degradation: Error connecting to local LLM: {str(e)}"

def create_file(filename, content=""):
    path = os.path.join(OUTPUT_DIR, os.path.basename(filename)) # prevent traversal
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File '{filename}' created in the output directory."
    except Exception as e:
        return f"Error creating file '{filename}': {str(e)}"

def write_code(filename, instructions):
    prompt = f"Write the code for the following request. Reply ONLY with the exact code, no markdown formatted block wrappers like ```python, and no explanations.\n\nRequest: {instructions}"
    code_content = generate_llm_response(prompt)
    
    # Strip markdown code blocks just in case the LLM outputs them anyway
    if code_content.startswith("```"):
        first_newline = code_content.find("\n")
        if first_newline != -1:
            code_content = code_content[first_newline+1:]
    if code_content.endswith("```"):
        code_content = code_content[:-3]
    code_content = code_content.strip()
    
    if not code_content:
        return "Graceful Degradation: Failed to generate valid code from LLM."

    path = os.path.join(OUTPUT_DIR, os.path.basename(filename)) # prevent traversal
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(code_content)
        return f"Code generated and written to '{filename}'.\n\nPreview:\n{code_content[:200]}..."
    except Exception as e:
        return f"Error writing code to '{filename}': {str(e)}"

def summarize_text(text):
    prompt = f"Summarize the following text briefly and concisely:\n\n{text}"
    return generate_llm_response(prompt)

def general_chat(text, chat_history=""):
    prompt = f"Respond helpfully to the user:\n\n{text}"
    return generate_llm_response(prompt, chat_history)