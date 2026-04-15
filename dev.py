import webbrowser
import os
import sys
from pathlib import Path

def launch():
    # Configuration
    url = "http://localhost:8000"
    output_dir = Path(__file__).resolve().parent / "output"
    
    # 1. Print the professional dashboard (No Unicode/Emojis for CP1252 compatibility)
    print("\n" + "="*50)
    print("      [V]  VOICE AI AGENT -- DEVELOPMENT SERVER")
    print(" " + "-"*48)
    print(f"  > Local URL: {url}")
    print(f"  > Storage:   {output_dir}")
    print(" " + "-"*48)
    print("  >> Opening browser automatically...")
    print("="*50 + "\n")

    # 2. Automatically open the browser
    try:
        webbrowser.open(url)
        print("  [SUCCESS] Redirected successfully!")
    except Exception as e:
        print(f"  [ERROR] Could not open browser: {e}")
        print(f"  Please manually visit: {url}")

if __name__ == "__main__":
    launch()
