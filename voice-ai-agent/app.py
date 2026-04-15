import streamlit as st
import os
import time

from stt import transcribe_audio
from intent import classify_intent
from tools import create_file, write_code, summarize_text, general_chat
from utils import extract_filename

# Ensure output folder exists
if not os.path.exists("output"):
    os.makedirs("output")

st.set_page_config(page_title="Voice AI Agent", page_icon="🎙", layout="wide")

# Persistent memory initialization
if "chat_memory" not in st.session_state:
    st.session_state.chat_memory = []
if "pending_actions" not in st.session_state:
    st.session_state.pending_actions = []

st.title("🎙 Voice AI Agent")

# Sidebar for memory and benchmarks
with st.sidebar:
    st.header("🗂 Session Memory")
    if len(st.session_state.chat_memory) == 0:
        st.write("No memory yet.")
    else:
        for idx, mem in enumerate(st.session_state.chat_memory):
            role = "User" if mem["role"] == "user" else "Agent"
            st.markdown(f"**{role}:** {mem['content']}")
            
    if st.button("Clear Memory"):
        st.session_state.chat_memory = []
        st.rerun()

input_method = st.radio("Choose Input Method", ["Microphone", "Upload File"], horizontal=True)

audio_data = None
if input_method == "Upload File":
    audio_data = st.file_uploader("Upload Audio", type=["wav", "mp3", "m4a", "ogg"])
else:
    audio_data = st.audio_input("Record Audio")

if audio_data:
    file_path = "temp_audio.wav"

    with open(file_path, "wb") as f:
        f.write(audio_data.read())

    # --- STEP 1: Transcription ---
    st.subheader("📝 Transcribed Text")
    t0 = time.time()
    with st.spinner("Transcribing..."):
        text = transcribe_audio(file_path)
    t1 = time.time()
    
    if not text or "Error" in text:
        st.error(f"Graceful Degradation: Could not transcribe audio properly: {text}")
        st.stop()
        
    st.write(text)
    st.caption(f"⏱ STT Time: {t1 - t0:.2f}s")
    
    # Save user query to memory
    if not st.session_state.chat_memory or st.session_state.chat_memory[-1]["role"] != "user" or st.session_state.chat_memory[-1]["content"] != text:
        st.session_state.chat_memory.append({"role": "user", "content": text})

    # --- STEP 2: Intent Detection ---
    st.subheader("🧠 Detected Intent(s)")
    t2 = time.time()
    with st.spinner("Classifying intent..."):
        intents = classify_intent(text)
    t3 = time.time()
    
    st.write(", ".join(intents))
    st.caption(f"⏱ Intent Classification Time: {t3 - t2:.2f}s")
    
    if len(intents) > 1:
        st.info("⚡ Compound Command Detected! Executing multiple steps.")

    # Convert intents into runnable actions
    actions_to_run = []
    
    for intent in intents:
        if intent == "create_file":
            filename = extract_filename(text)
            actions_to_run.append({
                "intent": intent,
                "name": f"Create File: {filename}",
                "requires_confirm": True,
                "func": create_file,
                "args": (filename, "Generated via voice AI agent.")
            })
        elif intent == "write_code":
            filename = extract_filename(text)
            actions_to_run.append({
                "intent": intent,
                "name": f"Write Code: {filename}",
                "requires_confirm": True,
                "func": write_code,
                "args": (filename, text)
            })
        elif intent == "summarize":
            actions_to_run.append({
                "intent": intent,
                "name": "Summarize Text",
                "requires_confirm": False,
                "func": summarize_text,
                "args": (text,)
            })
        else: # chat
            chat_context = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_memory])
            actions_to_run.append({
                "intent": intent,
                "name": "General Chat",
                "requires_confirm": False,
                "func": general_chat,
                "args": (text, chat_context)
            })

    # --- STEP 3: Execution & Human-in-the-Loop ---
    st.subheader("⚙️ Action Execution")
    
    total_output = ""
    start_exec_time = time.time()
    
    for idx, act in enumerate(actions_to_run):
        st.markdown(f"### Action {idx+1}: {act['name']}")
        
        # Human in the loop checks
        if act["requires_confirm"]:
            st.warning(f"⚠️ This action modifies your files. Do you want to allow it?")
            col1, col2 = st.columns(2)
            allow = col1.checkbox(f"Allow {act['name']}", key=f"allow_{idx}_{text}")
            skip = col2.checkbox(f"Skip {act['name']}", key=f"skip_{idx}_{text}")
            
            if skip:
                st.info("Action skipped by user.")
                continue
            if not allow:
                st.stop() # Wait for user to check the box
                
        # Execute Action
        with st.spinner(f"Executing {act['name']}..."):
            try:
                res = act["func"](*act["args"])
            except Exception as e:
                res = f"Graceful Degradation: Tool naturally failed: {str(e)}"
        
        st.success("Completed!")
        st.markdown(f"**Result:**\n{res}")
        st.divider()
        total_output += f"[{act['name']}] -> {res}\n\n"
        
    end_exec_time = time.time()
    st.caption(f"⏱ Action Execution Pipeline Time: {end_exec_time - start_exec_time:.2f}s")
    
    # Save agent response to memory
    if total_output:
        st.session_state.chat_memory.append({"role": "agent", "content": total_output})