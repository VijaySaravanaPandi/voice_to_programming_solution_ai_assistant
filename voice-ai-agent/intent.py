import requests
import json
import logging

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

def classify_intent(text):
    """
    Classifies intent of the provided text into a list of actions (Compound Commands!).
    """
    prompt = f"""
Analyze the following text and classify the user's intent into ONE OR MORE of these exact categories:
- create_file
- write_code
- summarize
- chat

Text: "{text}"

Reply with ONLY the intent category names separated by commas (e.g., summarize,create_file).
"""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        raw_intents = response.json().get("response", "").strip().lower()
        
        valid_intents = ["create_file", "write_code", "summarize", "chat"]
        detected = []
        for valid in valid_intents:
            if valid in raw_intents:
                detected.append(valid)
                
        if detected:
            return detected
        return ["chat"]
    except Exception as e:
        logging.error(f"Error calling Ollama in classify_intent: {e}")
        # Graceful degradation
        return _fallback_classify(text)

def _fallback_classify(text):
    text = text.lower()
    intents = []
    if "summarize" in text:
        intents.append("summarize")
    if "write code" in text or "function" in text:
        intents.append("write_code")
    if "create file" in text or "new file" in text or "save" in text:
        intents.append("create_file")
    
    if intents:
        return intents
    return ["chat"]