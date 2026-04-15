/**
 * VoiceAgent AI — Frontend JavaScript
 * Clean version: Compound commands, Memory, Benchmarks, Confirmation Dialog.
 */

const API = 'http://localhost:8000';

// -- State --
let mediaRecorder = null;
let audioChunks   = [];
let recordingTimer = null;
let recordingSeconds = 0;
let recordedBlob  = null;
let selectedFile  = null;
let pendingPayload = null;

// -- DOM refs --
const statusPill    = document.getElementById('statusPill');
const statusText    = document.getElementById('statusText');
const tabMic        = document.getElementById('tabMic');
const tabFile       = document.getElementById('tabFile');
const paneMic       = document.getElementById('paneMic');
const paneFile      = document.getElementById('paneFile');
const micBtn        = document.getElementById('micBtn');
const micVisualizer = document.getElementById('micVisualizer');
const micHint       = document.getElementById('micHint');
const recordingTimerEl = document.getElementById('recordingTimer');
const timerDisplay  = document.getElementById('timerDisplay');
const audioPreview  = document.getElementById('audioPreview');
const audioPlayer   = document.getElementById('audioPlayer');
const submitMicBtn  = document.getElementById('submitMicBtn');
const retryMicBtn   = document.getElementById('retryMicBtn');
const dropzone      = document.getElementById('dropzone');
const audioFileInput = document.getElementById('audioFileInput');
const fileSelected  = document.getElementById('fileSelected');
const selectedFileName = document.getElementById('selectedFileName');
const selectedFileSize = document.getElementById('selectedFileSize');
const submitFileBtn = document.getElementById('submitFileBtn');
const historyToggle = document.getElementById('historyToggle');
const filesToggle   = document.getElementById('filesToggle');
const historySidebar = document.getElementById('historySidebar');
const filesSidebar  = document.getElementById('filesSidebar');
const clearHistory  = document.getElementById('clearHistory');
const historyItems  = document.getElementById('historyItems');
const filesItems    = document.getElementById('filesItems');
const refreshFiles  = document.getElementById('refreshFiles');
const confirmDialog = document.getElementById('confirmDialog');
const confirmMessage = document.getElementById('confirmMessage');
const confirmCancel = document.getElementById('confirmCancel');
const confirmOk     = document.getElementById('confirmOk');
const fileModal     = document.getElementById('fileModal');
const modalTitle    = document.getElementById('modalTitle');
const modalCode     = document.getElementById('modalCode');
const modalClose    = document.getElementById('modalClose');
const toastContainer = document.getElementById('toastContainer');
const memoryBadge   = document.getElementById('memoryBadge');
const benchmarkPanel = document.getElementById('benchmarkPanel');

// -- Tabs --
function activateTab(tab, pane) {
  [tabMic, tabFile].forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
  [paneMic, paneFile].forEach(p => p.classList.remove('active'));
  tab.classList.add('active');
  tab.setAttribute('aria-selected', 'true');
  pane.classList.add('active');
}
tabMic.addEventListener('click',  () => activateTab(tabMic,  paneMic));
tabFile.addEventListener('click', () => activateTab(tabFile, paneFile));

// -- Status --
function setStatus(state, text) {
  statusPill.className = 'status-pill ' + (state || '');
  statusText.textContent = text;
}

// -- Mic --
micBtn.addEventListener('click', toggleRecording);

async function toggleRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    const mimeType = getSupportedMimeType();
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
      const url = URL.createObjectURL(recordedBlob);
      audioPlayer.src = url;
      audioPreview.classList.remove('hidden');
      stream.getTracks().forEach(t => t.stop());
    };

    mediaRecorder.start(100);
    setRecordingUI(true);
    startTimer();
    setStatus('processing', 'Recording...');
  } catch (err) {
    toast('Microphone access denied.', 'error');
    setStatus('error', 'Mic error');
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  setRecordingUI(false);
  stopTimer();
  setStatus('', 'Ready');
}

function getSupportedMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'];
  return types.find(t => MediaRecorder.isTypeSupported(t)) || '';
}

function setRecordingUI(recording) {
  micBtn.classList.toggle('recording', recording);
  micVisualizer.classList.toggle('recording', recording);
  micBtn.querySelector('.mic-icon').classList.toggle('hidden', recording);
  micBtn.querySelector('.stop-icon').classList.toggle('hidden', !recording);
  micHint.textContent = recording ? 'Click to stop recording' : 'Click the microphone to start recording';
  recordingTimerEl.classList.toggle('hidden', !recording);
  if (!recording) audioPreview.classList.add('hidden');
}

function startTimer() {
  recordingSeconds = 0;
  timerDisplay.textContent = '0:00';
  recordingTimer = setInterval(() => {
    recordingSeconds++;
    const m = Math.floor(recordingSeconds / 60);
    const s = String(recordingSeconds % 60).padStart(2, '0');
    timerDisplay.textContent = `${m}:${s}`;
  }, 1000);
}

function stopTimer() { clearInterval(recordingTimer); }

retryMicBtn.addEventListener('click', () => {
  audioPreview.classList.add('hidden');
  recordedBlob = null;
  setStatus('', 'Ready');
});

submitMicBtn.addEventListener('click', () => {
  if (!recordedBlob) return;
  const file = new File([recordedBlob], 'recording.webm', { type: recordedBlob.type });
  showConfirmDialog(`Process recording?`, () => processAudio(file));
});

// -- File Upload --
dropzone.addEventListener('click', () => audioFileInput.click());
audioFileInput.addEventListener('change', () => {
  if (audioFileInput.files[0]) handleFileSelected(audioFileInput.files[0]);
});

function handleFileSelected(file) {
  selectedFile = file;
  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = formatBytes(file.size);
  dropzone.classList.add('hidden');
  fileSelected.classList.remove('hidden');
}

submitFileBtn.addEventListener('click', () => {
  if (!selectedFile) return;
  showConfirmDialog(`Process "${selectedFile.name}"?`, () => processAudio(selectedFile));
});

// -- Confirm --
function showConfirmDialog(message, onConfirm) {
  confirmMessage.textContent = message;
  confirmDialog.classList.remove('hidden');
  pendingPayload = { onConfirm };
}
confirmCancel.addEventListener('click', () => { confirmDialog.classList.add('hidden'); pendingPayload = null; });
confirmOk.addEventListener('click', () => {
  confirmDialog.classList.add('hidden');
  if (pendingPayload) pendingPayload.onConfirm();
  pendingPayload = null;
});

// -- Core Processing --
async function processAudio(file) {
  resetPipeline();
  setStatus('processing', 'Processing...');
  setStepLoading('stt');

  const formData = new FormData();
  formData.append('audio', file);

  try {
    const resp = await fetch(`${API}/api/process`, { method: 'POST', body: formData });
    const result = await resp.json();
    renderPipelineResult(result);
    addToHistory(result);
    if (result.status === 'success') loadFiles();
    updateMemoryBadge();
  } catch (err) {
    setStatus('error', 'Error');
    setStepError('stt', err.message);
  }
}

// -- Pipeline --
function resetPipeline() {
  ['stt', 'intent', 'tool', 'result'].forEach(s => {
    document.getElementById(`step-${s}`).className = 'pipeline-step' + (s === 'result' ? ' step-result' : '');
    document.getElementById(`badge-${s}`).className = 'step-badge';
    document.getElementById(`body-${s}`).innerHTML = '';
  });
  document.getElementById('pipelineMeta').textContent = '';
  if (benchmarkPanel) benchmarkPanel.classList.add('hidden');
}

function setStepLoading(step) {
  document.getElementById(`step-${step}`).classList.add('active');
  document.getElementById(`badge-${step}`).className = 'step-badge loading';
  document.getElementById(`badge-${step}`).textContent = 'Processing…';
}

function setStepDone(step, html) {
  const el = document.getElementById(`step-${step}`);
  el.classList.remove('active');
  el.classList.add('done');
  document.getElementById(`badge-${step}`).className = 'step-badge success';
  document.getElementById(`badge-${step}`).textContent = '✓ Done';
  document.getElementById(`body-${step}`).innerHTML = html;
}

function setStepError(step, message) {
  const el = document.getElementById(`step-${step}`);
  el.classList.add('errored');
  document.getElementById(`badge-${step}`).className = 'step-badge error';
  document.getElementById(`badge-${step}`).textContent = '✗ Error';
  document.getElementById(`body-${step}`).innerHTML = `<p>${message}</p>`;
}

function renderPipelineResult(result) {
  const { transcription, intent, intent_details, action_taken, output, status, benchmarks } = result;

  if (transcription) setStepDone('stt', `<div class="step-transcription">${transcription}</div>`);
  else return setStepError('stt', 'Transcription failed');

  if (intent) {
    let compoundHtml = '';
    if (intent_details?.is_compound) {
      compoundHtml = `<div class="compound-banner">⚡ Compound Command Detected</div>`;
    }
    setStepDone('intent', `<div class="intent-pill ${intent}">${intent}</div>${compoundHtml}`);
  }

  if (action_taken) setStepDone('tool', `<div class="action-tag">${action_taken}</div>`);
  
  if (status === 'success' && output) setStepDone('result', `<div class="output-content">${output}</div>`);
  
  if (benchmarks) renderBenchmarks(benchmarks, intent_details?.llm_used);
  setStatus('', 'Ready');
}

function renderBenchmarks(benchmarks, llm) {
  if (!benchmarkPanel) return;
  benchmarkPanel.innerHTML = `<table><tr><th>Stage</th><th>Latency</th></tr>
    <tr><td>STT</td><td>${benchmarks.stt_ms}ms</td></tr>
    <tr><td>Intent</td><td>${benchmarks.intent_ms}ms</td></tr>
    <tr><td>Total</td><td>${benchmarks.total_ms}ms</td></tr></table>`;
  benchmarkPanel.classList.remove('hidden');
}

async function updateMemoryBadge() {
  const resp = await fetch(`${API}/api/memory`);
  const data = await resp.json();
  if (data.count > 0) {
    memoryBadge.textContent = `🧠 ${Math.floor(data.count/2)} Memory`;
    memoryBadge.classList.remove('hidden');
  }
}

// -- History & Files --
function addToHistory(result) {
  const item = document.createElement('div');
  item.className = 'history-item';
  item.innerHTML = `<p>${result.transcription}</p>`;
  historyItems.prepend(item);
}

async function loadFiles() {
  const resp = await fetch(`${API}/api/files`);
  const data = await resp.json();
  filesItems.innerHTML = '';
  data.files.forEach(f => {
    const item = document.createElement('div');
    item.className = 'file-item';
    item.textContent = f.name;
    filesItems.appendChild(item);
  });
}

function toast(msg, type) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function formatBytes(b) { return b < 1024 ? `${b} B` : `${(b/1024).toFixed(1)} KB`; }

// -- Init --
historyToggle.addEventListener('click', () => historySidebar.classList.toggle('open'));
filesToggle.addEventListener('click', () => filesSidebar.classList.toggle('open'));
loadFiles();
updateMemoryBadge();
