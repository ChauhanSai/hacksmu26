/**
 * Audio Cleanup Terminal — Frontend Logic
 * Two-phase UI: upload-only, then full-page results.
 */

const API_BASE = 'http://127.0.0.1:5000';

const form = document.getElementById('cleanup-form');
const phaseUpload = document.getElementById('phase-upload');
const phaseResults = document.getElementById('phase-results');
const audioInput = document.getElementById('audio-input');
const dropzone = document.getElementById('dropzone');
const selectedFile = document.getElementById('selected-file');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');
const clearFile = document.getElementById('clear-file');
const processBtn = document.getElementById('process-btn');
const processing = document.getElementById('processing');
const progressBar = document.getElementById('progress-bar');
const progressPercent = document.getElementById('progress-percent');
const progressStatus = document.getElementById('progress-status');
const errorPanel = document.getElementById('error-panel');
const errorMessage = document.getElementById('error-message');
const summaryText = document.getElementById('summary-text');
const beforeSpectrogram = document.getElementById('before-spectrogram');
const afterSpectrogram = document.getElementById('after-spectrogram');
const segmentsSection = document.getElementById('segments-section');
const timelineContainer = document.getElementById('timeline-container');
const timelineAxis = document.getElementById('timeline-axis');
const segmentsDurationHint = document.getElementById('segments-duration-hint');
const segmentsList = document.getElementById('segments-list');
const cleanedAudio = document.getElementById('cleaned-audio');
const playbackStatus = document.getElementById('playback-status');
const downloadAudio = document.getElementById('download-audio');
const downloadSpectrogram = document.getElementById('download-spectrogram');
const newUploadBtn = document.getElementById('new-upload-btn');
const audioPlayBtn = document.getElementById('audio-play-btn');
const audioIconPlay = document.getElementById('audio-icon-play');
const audioIconPause = document.getElementById('audio-icon-pause');
const audioSeekWrap = document.getElementById('audio-seek-wrap');
const audioSeekBar = document.getElementById('audio-seek-bar');
const audioSeekFill = document.getElementById('audio-seek-fill');
const audioTimeCurrent = document.getElementById('audio-time-current');
const audioTimeDuration = document.getElementById('audio-time-duration');
const processingHeadline = document.getElementById('processing-headline');
const recordBtn = document.getElementById('record-btn');
const recordBtnText = document.getElementById('record-btn-text');
const recordIconMic = document.getElementById('record-icon-mic');
const recordIconStop = document.getElementById('record-icon-stop');
const recordingIndicator = document.getElementById('recording-indicator');
const recordingTime = document.getElementById('recording-time');
const recordingVisualizer = document.getElementById('recording-visualizer');
const analyzeBtn = document.getElementById('analyze-btn');

let mediaRecorder = null;
let audioChunks = [];
let recordingStartTime = null;
let recordingTimer = null;
let audioContext = null;
let analyser = null;
let visualizerAnimationId = null;
let lastProcessedData = null;

/** Labels must stay in sync with `#pipeline-steps` in cleanup.html */
const PIPELINE_STEPS = [
  { title: 'Upload & ingest', detail: 'Load WAV and validate' },
  { title: 'Input spectrogram', detail: 'Time–frequency view of raw audio' },
  { title: 'Rumble detection', detail: '8–180 Hz candidate windows' },
  { title: 'Noise profile', detail: 'Estimate background from non-rumble regions' },
  { title: 'Spectral cleanup', detail: 'Subtraction + tonal notch filters' },
  { title: 'Export assets', detail: 'Clean WAV + before/after spectrograms' },
];

const PIPELINE_MS_PER_STEP = 2200;

let currentFile = null;
let segments = [];
let seekPointerActive = false;
let pipelineStepTimer = null;
let pipelineStepEls = null;
let isRecording = false;

function getPipelineStepEls() {
  if (!pipelineStepEls) {
    pipelineStepEls = Array.from(document.querySelectorAll('#pipeline-steps .pipeline-step'));
  }
  return pipelineStepEls;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clearPipelineTimer() {
  if (pipelineStepTimer) {
    clearInterval(pipelineStepTimer);
    pipelineStepTimer = null;
  }
}

function resetPipelineStepsUI() {
  clearPipelineTimer();
  getPipelineStepEls().forEach((el) => {
    el.classList.remove('pipeline-step--active', 'pipeline-step--done');
    el.classList.add('pipeline-step--pending');
  });
}

function setPipelineActiveStep(activeIndex) {
  const els = getPipelineStepEls();
  els.forEach((el, i) => {
    el.classList.remove('pipeline-step--active', 'pipeline-step--done', 'pipeline-step--pending');
    if (i < activeIndex) el.classList.add('pipeline-step--done');
    else if (i === activeIndex) el.classList.add('pipeline-step--active');
    else el.classList.add('pipeline-step--pending');
  });
}

function completePipelineSteps() {
  getPipelineStepEls().forEach((el) => {
    el.classList.remove('pipeline-step--active', 'pipeline-step--pending');
    el.classList.add('pipeline-step--done');
  });
}

function pipelineStatusLine(i) {
  const s = PIPELINE_STEPS[i];
  return `${s.title} — ${s.detail}`;
}

function pipelineProgressPercent(stepIndex) {
  return 5 + ((stepIndex + 1) / PIPELINE_STEPS.length) * 75;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

function formatTimeSeconds(s) {
  if (!Number.isFinite(s) || s < 0) return '0.00 s';
  if (s < 60) return `${s.toFixed(2)} s`;
  const m = Math.floor(s / 60);
  const sec = s - m * 60;
  return `${m}:${sec < 10 ? '0' : ''}${sec.toFixed(1)}`;
}

function formatPlayerClock(sec) {
  if (!Number.isFinite(sec) || sec < 0) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function syncPlayerUi() {
  const el = cleanedAudio;
  const dur = el.duration;
  const cur = el.currentTime;
  if (audioTimeCurrent) audioTimeCurrent.textContent = formatPlayerClock(cur);
  if (audioTimeDuration) {
    audioTimeDuration.textContent = Number.isFinite(dur) ? formatPlayerClock(dur) : '0:00';
  }
  if (audioSeekFill && Number.isFinite(dur) && dur > 0) {
    audioSeekFill.style.width = `${(cur / dur) * 100}%`;
  }
  if (audioSeekBar) {
    const pct = Number.isFinite(dur) && dur > 0 ? Math.round((cur / dur) * 100) : 0;
    audioSeekBar.setAttribute('aria-valuenow', String(pct));
  }
}

function setPlayerPlaying(playing) {
  if (!audioIconPlay || !audioIconPause || !audioPlayBtn) return;
  audioIconPlay.classList.toggle('hidden', playing);
  audioIconPause.classList.toggle('hidden', !playing);
  audioPlayBtn.setAttribute('aria-label', playing ? 'Pause' : 'Play');
}

function seekFromClientX(clientX) {
  if (!audioSeekBar || !Number.isFinite(cleanedAudio.duration) || cleanedAudio.duration <= 0) return;
  const rect = audioSeekBar.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  cleanedAudio.currentTime = ratio * cleanedAudio.duration;
  syncPlayerUi();
}

function handleFileSelect(file) {
  if (!file) return;

  if (!file.name.toLowerCase().endsWith('.wav')) {
    showError('Only WAV audio files are supported.');
    return;
  }

  if (file.size > 200 * 1024 * 1024) {
    showError('File size exceeds 200 MB limit.');
    return;
  }

  currentFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);

  dropzone.classList.add('hidden');
  selectedFile.classList.remove('hidden');
  processBtn.disabled = false;
  hideError();
}

function clearSelectedFile() {
  currentFile = null;
  audioInput.value = '';
  dropzone.classList.remove('hidden');
  selectedFile.classList.add('hidden');
  processBtn.disabled = true;
}

function showError(message) {
  errorMessage.textContent = message;
  errorPanel.classList.remove('hidden');
}

function hideError() {
  errorPanel.classList.add('hidden');
}

function updateProgress(percent, status) {
  const p = Math.min(100, Math.max(0, percent));
  progressBar.style.width = `${p}%`;
  if (progressPercent) progressPercent.textContent = `${Math.round(p)}%`;
  progressStatus.textContent = status;
}

function showProcessing() {
  processing.classList.remove('hidden');
  processBtn.disabled = true;
  if (processingHeadline) processingHeadline.textContent = 'Live pipeline';
  resetPipelineStepsUI();
  setPipelineActiveStep(0);
  updateProgress(5, pipelineStatusLine(0));
}

function hideProcessing() {
  clearPipelineTimer();
  processing.classList.add('hidden');
  processBtn.disabled = !currentFile;
  if (processingHeadline) processingHeadline.textContent = 'Pipeline';
}

function renderTimelineAxis(duration) {
  if (!timelineAxis) return;
  timelineAxis.innerHTML = '';
  const dur = Math.max(duration || 0, 1e-6);
  const steps = 5;
  for (let i = 0; i <= steps; i++) {
    const t = (dur * i) / steps;
    const span = document.createElement('span');
    span.textContent = formatTimeSeconds(t);
    timelineAxis.appendChild(span);
  }
}

function renderSegments(segs, duration) {
  segments = segs;

  if (!segs || segs.length === 0) {
    segmentsSection.classList.add('hidden');
    return;
  }

  segmentsSection.classList.remove('hidden');
  if (segmentsDurationHint) {
    segmentsDurationHint.textContent = `${segs.length} window${segs.length === 1 ? '' : 's'} · ${formatTimeSeconds(duration)} total`;
  }

  renderTimelineAxis(duration);

  timelineContainer.innerHTML = '';
  segmentsList.innerHTML = '';

  const dur = Math.max(duration, 1e-6);

  segs.forEach((seg, i) => {
    const startPct = (seg.start / dur) * 100;
    const widthPct = Math.max(((seg.end - seg.start) / dur) * 100, 0.35);
    const name = seg.label || `Rumble ${i + 1}`;
    const spanSec = Math.max(0, seg.end - seg.start);

    const bar = document.createElement('div');
    bar.className =
      'absolute top-0 bottom-0 rounded-sm bg-[color:var(--accent)] opacity-70 transition-opacity duration-200';
    bar.style.left = `${startPct}%`;
    bar.style.width = `${widthPct}%`;
    bar.dataset.index = String(i);
    bar.title = `${name} · ${spanSec.toFixed(2)}s · ${seg.start.toFixed(2)}s–${seg.end.toFixed(2)}s`;
    timelineContainer.appendChild(bar);

    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'cleanup-segment-row';
    row.dataset.index = String(i);

    const typeEl = document.createElement('span');
    typeEl.className = 'cleanup-segment-row__type';
    typeEl.textContent = name;

    const timeWrap = document.createElement('div');
    timeWrap.className = 'cleanup-segment-row__meta';
    const timeEl = document.createElement('span');
    timeEl.className = 'cleanup-segment-row__time mono';
    timeEl.textContent = `${seg.start.toFixed(2)}s – ${seg.end.toFixed(2)}s`;
    const durEl = document.createElement('span');
    durEl.className = 'cleanup-segment-row__dur';
    durEl.textContent = `${spanSec.toFixed(2)} s span`;
    timeWrap.appendChild(timeEl);
    timeWrap.appendChild(durEl);

    const goEl = document.createElement('span');
    goEl.className = 'cleanup-segment-row__go';
    goEl.textContent = 'Jump';

    row.appendChild(typeEl);
    row.appendChild(timeWrap);
    row.appendChild(goEl);

    row.addEventListener('click', () => {
      cleanedAudio.currentTime = seg.start;
      cleanedAudio.play();
    });
    segmentsList.appendChild(row);
  });
}

function updatePlaybackStatus() {
  syncPlayerUi();
  const current = cleanedAudio.currentTime;
  let activeSegment = null;

  segments.forEach((seg, i) => {
    const bars = timelineContainer.querySelectorAll(`[data-index="${i}"]`);
    const pills = segmentsList.querySelectorAll(`[data-index="${i}"]`);
    const isActive = current >= seg.start && current <= seg.end;

    bars.forEach((bar) => {
      bar.classList.toggle('opacity-100', isActive);
      bar.classList.toggle('opacity-70', !isActive);
    });

    pills.forEach((pill) => {
      pill.classList.toggle('cleanup-segment-row--active', isActive);
    });

    if (isActive) activeSegment = i + 1;
  });

  if (activeSegment) {
    const seg = segments[activeSegment - 1];
    const name = seg.label || `Rumble ${activeSegment}`;
    playbackStatus.textContent = `Playing · ${name} · ${current.toFixed(1)}s`;
  } else {
    playbackStatus.textContent = `Position ${current.toFixed(1)}s (outside detected windows)`;
  }
}

function showResultsPhase() {
  phaseUpload.classList.add('cleanup-phase-leave');
  window.setTimeout(() => {
    hideProcessing();
    phaseUpload.classList.add('hidden');
    phaseUpload.classList.remove('cleanup-phase-leave');
    phaseResults.classList.remove('hidden');
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        phaseResults.classList.remove('opacity-0');
        phaseResults.classList.add('cleanup-phase-enter-active');
      });
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, 280);
}

function showUploadPhase() {
  phaseResults.classList.remove('cleanup-phase-enter-active');
  phaseResults.classList.add('opacity-0');
  window.setTimeout(() => {
    phaseResults.classList.add('hidden');
    phaseUpload.classList.remove('hidden');
    requestAnimationFrame(() => {
      phaseUpload.classList.remove('opacity-0');
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, 200);
}

function resetResultsView() {
  cleanedAudio.pause();
  cleanedAudio.removeAttribute('src');
  beforeSpectrogram.removeAttribute('src');
  afterSpectrogram.removeAttribute('src');
  downloadAudio.removeAttribute('href');
  downloadSpectrogram.removeAttribute('href');
  segmentsList.innerHTML = '';
  timelineContainer.innerHTML = '';
  if (timelineAxis) timelineAxis.innerHTML = '';
  segments = [];
  segmentsSection.classList.add('hidden');
  setPlayerPlaying(false);
  if (audioSeekFill) audioSeekFill.style.width = '0%';
  if (audioTimeCurrent) audioTimeCurrent.textContent = '0:00';
  if (audioTimeDuration) audioTimeDuration.textContent = '0:00';
}

async function processAudio() {
  if (!currentFile) return;

  showProcessing();
  hideError();

  let stepIdx = 0;

  pipelineStepTimer = window.setInterval(() => {
    if (stepIdx < PIPELINE_STEPS.length - 1) {
      stepIdx += 1;
      setPipelineActiveStep(stepIdx);
      updateProgress(pipelineProgressPercent(stepIdx), pipelineStatusLine(stepIdx));
    } else {
      clearPipelineTimer();
    }
  }, PIPELINE_MS_PER_STEP);

  const formData = new FormData();
  formData.append('audio', currentFile);

  try {
    const response = await fetch(`${API_BASE}/api/clean`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Server error: ${response.status}`);
    }

    const data = await response.json();

    if (data.error) {
      throw new Error(data.error);
    }

    clearPipelineTimer();

    while (stepIdx < PIPELINE_STEPS.length - 1) {
      stepIdx += 1;
      setPipelineActiveStep(stepIdx);
      updateProgress(pipelineProgressPercent(stepIdx), pipelineStatusLine(stepIdx));
      await sleep(160);
    }

    completePipelineSteps();
    updateProgress(100, 'Complete — opening results');
    await sleep(480);

    hideProcessing();
    displayResults(data);
  } catch (error) {
    clearPipelineTimer();
    resetPipelineStepsUI();
    hideProcessing();
    showError(error.message || 'Failed to process audio. Is the backend running?');
    console.error('Processing error:', error);
  }
}

audioInput.addEventListener('change', (e) => {
  handleFileSelect(e.target.files[0]);
});

clearFile.addEventListener('click', clearSelectedFile);

form.addEventListener('submit', (e) => {
  e.preventDefault();
  processAudio();
});

newUploadBtn.addEventListener('click', () => {
  resetResultsView();
  clearSelectedFile();
  hideError();
  showUploadPhase();
});

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('border-[color:var(--accent)]', 'bg-[color:var(--glass)]');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('border-[color:var(--accent)]', 'bg-[color:var(--glass)]');
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('border-[color:var(--accent)]', 'bg-[color:var(--glass)]');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

cleanedAudio.addEventListener('timeupdate', updatePlaybackStatus);
cleanedAudio.addEventListener('seeked', updatePlaybackStatus);
cleanedAudio.addEventListener('play', () => {
  setPlayerPlaying(true);
  updatePlaybackStatus();
});
cleanedAudio.addEventListener('pause', () => {
  setPlayerPlaying(false);
  updatePlaybackStatus();
});
cleanedAudio.addEventListener('ended', () => {
  setPlayerPlaying(false);
  syncPlayerUi();
  updatePlaybackStatus();
});
cleanedAudio.addEventListener('loadedmetadata', () => {
  const d = cleanedAudio.duration;
  if (Number.isFinite(d)) {
    playbackStatus.textContent = `Duration: ${d.toFixed(2)}s`;
  }
  syncPlayerUi();
});

if (audioPlayBtn) {
  audioPlayBtn.addEventListener('click', () => {
    if (cleanedAudio.paused) {
      cleanedAudio.play().catch(() => {});
    } else {
      cleanedAudio.pause();
    }
  });
}

if (audioSeekWrap && audioSeekBar) {
  audioSeekWrap.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    seekPointerActive = true;
    try {
      audioSeekWrap.setPointerCapture(e.pointerId);
    } catch (_) {
      /* ignore */
    }
    seekFromClientX(e.clientX);
  });
  audioSeekWrap.addEventListener('pointermove', (e) => {
    if (!seekPointerActive) return;
    seekFromClientX(e.clientX);
  });
  audioSeekWrap.addEventListener('pointerup', (e) => {
    seekPointerActive = false;
    try {
      audioSeekWrap.releasePointerCapture(e.pointerId);
    } catch (_) {
      /* ignore */
    }
  });
  audioSeekWrap.addEventListener('pointercancel', () => {
    seekPointerActive = false;
  });
  audioSeekBar.addEventListener('keydown', (e) => {
    const dur = cleanedAudio.duration;
    if (!Number.isFinite(dur) || dur <= 0) return;
    const step = 5;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      cleanedAudio.currentTime = Math.min(dur, cleanedAudio.currentTime + step);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      cleanedAudio.currentTime = Math.max(0, cleanedAudio.currentTime - step);
    }
    syncPlayerUi();
  });
}

// ════════════════════════════════════════════════════════════════
//  RECORDING FUNCTIONALITY
// ════════════════════════════════════════════════════════════════

function formatRecordingTime(ms) {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${String(sec).padStart(2, '0')}`;
}

function drawVisualizer() {
  if (!analyser || !recordingVisualizer) return;
  const ctx = recordingVisualizer.getContext('2d');
  const width = recordingVisualizer.width;
  const height = recordingVisualizer.height;
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    if (!isRecording) return;
    visualizerAnimationId = requestAnimationFrame(draw);
    analyser.getByteFrequencyData(dataArray);

    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
    ctx.fillRect(0, 0, width, height);

    const barWidth = (width / bufferLength) * 2.5;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const barHeight = (dataArray[i] / 255) * height;
      const red = 239;
      const green = 68 + (dataArray[i] / 255) * 50;
      const blue = 68;
      ctx.fillStyle = `rgb(${red}, ${green}, ${blue})`;
      ctx.fillRect(x, height - barHeight, barWidth, barHeight);
      x += barWidth + 1;
    }
  }
  draw();
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(track => track.stop());
      if (audioContext) {
        audioContext.close();
        audioContext = null;
      }
      
      const webmBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const wavBlob = await convertToWav(webmBlob);
      const file = new File([wavBlob], `recording_${Date.now()}.wav`, { type: 'audio/wav' });
      handleFileSelect(file);
    };

    mediaRecorder.start(100);
    isRecording = true;
    recordingStartTime = Date.now();

    recordBtn.classList.add('recording');
    recordBtnText.textContent = 'Stop Recording';
    recordIconMic.classList.add('hidden');
    recordIconStop.classList.remove('hidden');
    recordingIndicator.classList.remove('hidden');
    dropzone.classList.add('hidden');
    selectedFile.classList.add('hidden');

    if (recordingVisualizer) {
      recordingVisualizer.width = recordingVisualizer.offsetWidth;
      recordingVisualizer.height = recordingVisualizer.offsetHeight;
    }
    drawVisualizer();

    recordingTimer = setInterval(() => {
      const elapsed = Date.now() - recordingStartTime;
      recordingTime.textContent = formatRecordingTime(elapsed);
    }, 100);

  } catch (err) {
    console.error('Recording error:', err);
    showError('Could not access microphone. Please allow microphone permissions.');
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  isRecording = false;

  if (recordingTimer) {
    clearInterval(recordingTimer);
    recordingTimer = null;
  }
  if (visualizerAnimationId) {
    cancelAnimationFrame(visualizerAnimationId);
    visualizerAnimationId = null;
  }

  recordBtn.classList.remove('recording');
  recordBtnText.textContent = 'Record Audio';
  recordIconMic.classList.remove('hidden');
  recordIconStop.classList.add('hidden');
  recordingIndicator.classList.add('hidden');
}

async function convertToWav(webmBlob) {
  const arrayBuffer = await webmBlob.arrayBuffer();
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
  
  const numChannels = 1;
  const sampleRate = audioBuffer.sampleRate;
  const format = 1;
  const bitDepth = 16;
  
  const channelData = audioBuffer.getChannelData(0);
  const samples = channelData.length;
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  
  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
  
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + samples * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, format, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * bitDepth / 8, true);
  view.setUint16(32, numChannels * bitDepth / 8, true);
  view.setUint16(34, bitDepth, true);
  writeString(36, 'data');
  view.setUint32(40, samples * 2, true);
  
  let offset = 44;
  for (let i = 0; i < samples; i++) {
    const s = Math.max(-1, Math.min(1, channelData[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    offset += 2;
  }
  
  audioCtx.close();
  return new Blob([buffer], { type: 'audio/wav' });
}

if (recordBtn) {
  recordBtn.addEventListener('click', () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });
}

// ════════════════════════════════════════════════════════════════
//  ANALYZE BUTTON - OPEN REPORT PAGE
// ════════════════════════════════════════════════════════════════

function displayResults(data) {
  lastProcessedData = data;
  summaryText.textContent = data.summary_line || 'Processing complete.';

  beforeSpectrogram.src = data.before_image_url;
  afterSpectrogram.src = data.after_image_url;
  downloadSpectrogram.href = data.after_image_url;

  cleanedAudio.src = data.audio_url;
  downloadAudio.href = data.audio_url;
  downloadAudio.download = data.audio_download_name || 'cleaned_audio.wav';

  const duration = parseFloat(data.duration_seconds) || 0;
  playbackStatus.textContent = `Duration: ${duration.toFixed(2)}s`;
  setPlayerPlaying(false);
  syncPlayerUi();

  const segs = (data.segments || []).map((s) => ({
    start: parseFloat(s.start),
    end: parseFloat(s.end),
    label: typeof s.label === 'string' ? s.label : null,
  }));
  renderSegments(segs, duration);

  showResultsPhase();
}

if (analyzeBtn) {
  analyzeBtn.addEventListener('click', () => {
    if (!lastProcessedData) {
      showError('No processed audio to analyze. Please process an audio file first.');
      return;
    }
    
    const payload = JSON.stringify(lastProcessedData);
    sessionStorage.setItem('elephantAudioData', payload);
    try {
      localStorage.setItem('elephantAudioData', payload);
    } catch (_) { /* quota / private mode */ }
    window.open('audio-report.html', '_blank');
  });
}
