"""
Speech-to-Text Module
Uses Groq's Whisper API for fast, accurate transcription.
Falls back to a simple placeholder if API key not configured.
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


async def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio file to text.
    Primary: Groq Whisper API (whisper-large-v3)
    Fallback: Returns error message if no API key
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if GROQ_API_KEY:
        return await _transcribe_groq(audio_path)
    else:
        raise ValueError(
            "GROQ_API_KEY not set. Please add it to your .env file. "
            "Get a free key at https://console.groq.com"
        )


async def _transcribe_groq(audio_path: str) -> str:
    """Transcribe using Groq Whisper API"""
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        
        with open(audio_path, "rb") as audio_file:
            # Run in thread pool since groq client is sync
            loop = asyncio.get_event_loop()
            transcription = await loop.run_in_executor(
                None,
                lambda: client.audio.transcriptions.create(
                    file=(Path(audio_path).name, audio_file.read()),
                    model="whisper-large-v3",
                    response_format="text",
                    language="en",
                ),
            )
        
        # Groq returns a string when response_format="text"
        if isinstance(transcription, str):
            return transcription.strip()
        return transcription.text.strip()

    except ImportError:
        raise ImportError("groq package not installed. Run: pip install groq")
    except Exception as e:
        raise RuntimeError(f"Groq transcription failed: {e}")
