import requests

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

def extract_filename(text):
    prompt = f"""
Extract the requested filename from the text. If no explicit filename is mentioned, invent a concise and relevant one with the appropriate extension (.py for code, .txt for text).
Examples:
- "Create a Python file with a retry function called main.py" -> main.py
- "Write python code to scrape a site" -> scraper.py
- "Create a text file" -> new_file.txt

Text: "{text}"

Reply with ONLY the filename, nothing else.
"""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=5)
        response.raise_for_status()
        filename = response.json().get("response", "").strip()
        # Clean up any surrounding spaces or quotes
        filename = filename.replace('"', '').replace("'", "")
        # fallback if LLM answers weirdly
        if " " in filename or len(filename) > 30:
            return _fallback_extract(text)
        return filename
    except Exception:
        return _fallback_extract(text)

def _fallback_extract(text):
    words = text.split()
    for word in words:
        if ".py" in word or ".txt" in word:
            return word.strip(".,;:?!")
    if "python" in text.lower() or "code" in text.lower():
        return "script.py"
    return "file.txt"