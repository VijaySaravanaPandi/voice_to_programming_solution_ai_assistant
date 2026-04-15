"""
Quick setup verification script.
Run this to check all dependencies before starting the agent.
"""
import sys
import os

print("=" * 55)
print("  VoiceAgent AI — Setup Checker")
print("=" * 55)

errors = []
warnings = []

# Python version
major, minor = sys.version_info[:2]
if major < 3 or (major == 3 and minor < 9):
    errors.append(f"Python 3.9+ required, found {major}.{minor}")
else:
    print(f"✅ Python {major}.{minor}")

# Required packages
packages = [
    ("fastapi",          "fastapi"),
    ("uvicorn",          "uvicorn"),
    ("groq",             "groq"),
    ("httpx",            "httpx"),
    ("python-multipart", "multipart"),
    ("python-dotenv",    "dotenv"),
    ("aiofiles",         "aiofiles"),
]
for pkg_name, import_name in packages:
    try:
        __import__(import_name)
        print(f"✅ {pkg_name}")
    except ImportError:
        errors.append(f"Missing package: {pkg_name}  →  pip install {pkg_name}")

# .env file
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and groq_key != "your_groq_api_key_here":
        print("✅ GROQ_API_KEY set")
    else:
        errors.append("GROQ_API_KEY not set in .env file.\n     Get a free key at https://console.groq.com")
else:
    errors.append(".env file not found. Copy .env.example → .env and add your GROQ_API_KEY")

# Ollama (optional)
try:
    import httpx
    r = httpx.get("http://localhost:11434/api/tags", timeout=2)
    if r.status_code == 200:
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"✅ Ollama running — models: {', '.join(models) if models else 'none pulled'}")
        if not any("llama3" in m for m in models):
            warnings.append("llama3 not found in Ollama. Run: ollama pull llama3")
    else:
        warnings.append("Ollama is running but returned unexpected response")
except Exception:
    warnings.append("Ollama not running (optional). Will use Groq as LLM fallback.\n     Install: https://ollama.ai")

# output dir
output_dir = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(output_dir, exist_ok=True)
print(f"✅ output/ directory ready: {output_dir}")

print()
if warnings:
    print("⚠️  Warnings (non-critical):")
    for w in warnings:
        print(f"   • {w}")
    print()

if errors:
    print("❌ Errors (must fix):")
    for e in errors:
        print(f"   • {e}")
    print()
    print("Fix the above errors, then run: python backend/main.py")
    sys.exit(1)
else:
    print("🚀 All checks passed! Run:  python backend/main.py")
    print("   Then open:              http://localhost:8000")
