/**
 * Audio Cleanup Terminal — Frontend Logic
 * Handles file upload, API communication, and results display
 */

const API_BASE = 'http://127.0.0.1:5000';

// DOM Elements
const form = document.getElementById('cleanup-form');
const audioInput = document.getElementById('audio-input');
const dropzone = document.getElementById('dropzone');
const selectedFile = document.getElementById('selected-file');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');
const clearFile = document.getElementById('clear-file');
const processBtn = document.getElementById('process-btn');
const processing = document.getElementById('processing');
const progressBar = document.getElementById('progress-bar');
const progressStatus = document.getElementById('progress-status');
const errorPanel = document.getElementById('error-panel');
const errorMessage = document.getElementById('error-message');
const resultsEmpty = document.getElementById('results-empty');
const resultsContent = document.getElementById('results-content');
const summaryText = document.getElementById('summary-text');
const beforeSpectrogram = document.getElementById('before-spectrogram');
const afterSpectrogram = document.getElementById('after-spectrogram');
const segmentsSection = document.getElementById('segments-section');
const timelineContainer = document.getElementById('timeline-container');
const segmentsList = document.getElementById('segments-list');
const cleanedAudio = document.getElementById('cleaned-audio');
const playbackStatus = document.getElementById('playback-status');
const downloadAudio = document.getElementById('download-audio');
const downloadSpectrogram = document.getElementById('download-spectrogram');

let currentFile = null;
let segments = [];

// Format file size
function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Handle file selection
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

// Clear selected file
function clearSelectedFile() {
  currentFile = null;
  audioInput.value = '';
  dropzone.classList.remove('hidden');
  selectedFile.classList.add('hidden');
  processBtn.disabled = true;
}

// Show error
function showError(message) {
  errorMessage.textContent = message;
  errorPanel.classList.remove('hidden');
}

// Hide error
function hideError() {
  errorPanel.classList.add('hidden');
}

// Update progress
function updateProgress(percent, status) {
  progressBar.style.width = `${percent}%`;
  progressStatus.textContent = status;
}

// Show processing state
function showProcessing() {
  processing.classList.remove('hidden');
  processBtn.disabled = true;
  updateProgress(0, 'Uploading audio file...');
}

// Hide processing state
function hideProcessing() {
  processing.classList.add('hidden');
  processBtn.disabled = false;
}

// Render segments on timeline
function renderSegments(segs, duration) {
  segments = segs;
  
  if (!segs || segs.length === 0) {
    segmentsSection.classList.add('hidden');
    return;
  }
  
  segmentsSection.classList.remove('hidden');
  
  // Clear previous
  timelineContainer.innerHTML = '';
  segmentsList.innerHTML = '';
  
  // Render timeline bars
  segs.forEach((seg, i) => {
    const startPct = (seg.start / duration) * 100;
    const widthPct = Math.max(((seg.end - seg.start) / duration) * 100, 0.5);
    
    const bar = document.createElement('div');
    bar.className = 'absolute h-full bg-[color:var(--accent)] opacity-60 rounded';
    bar.style.left = `${startPct}%`;
    bar.style.width = `${widthPct}%`;
    bar.dataset.index = i;
    timelineContainer.appendChild(bar);
    
    // Render pill
    const pill = document.createElement('span');
    pill.className = 'tag tag-teal cursor-pointer transition-all hover:bg-[color:var(--accent-glow)]';
    pill.textContent = `Rumble ${i + 1}: ${seg.start.toFixed(2)}s – ${seg.end.toFixed(2)}s`;
    pill.dataset.index = i;
    pill.addEventListener('click', () => {
      cleanedAudio.currentTime = seg.start;
      cleanedAudio.play();
    });
    segmentsList.appendChild(pill);
  });
}

// Update playback status
function updatePlaybackStatus() {
  const current = cleanedAudio.currentTime;
  let activeSegment = null;
  
  segments.forEach((seg, i) => {
    const bars = timelineContainer.querySelectorAll(`[data-index="${i}"]`);
    const pills = segmentsList.querySelectorAll(`[data-index="${i}"]`);
    const isActive = current >= seg.start && current <= seg.end;
    
    bars.forEach(bar => {
      bar.classList.toggle('opacity-100', isActive);
      bar.classList.toggle('opacity-60', !isActive);
    });
    
    pills.forEach(pill => {
      pill.classList.toggle('tag-purple', isActive);
      pill.classList.toggle('tag-teal', !isActive);
    });
    
    if (isActive) activeSegment = i + 1;
  });
  
  if (activeSegment) {
    playbackStatus.textContent = `Current: Rumble ${activeSegment} · ${current.toFixed(1)}s`;
  } else {
    playbackStatus.textContent = `Position: ${current.toFixed(1)}s (outside rumble windows)`;
  }
}

// Display results
function displayResults(data) {
  resultsEmpty.classList.add('hidden');
  resultsContent.classList.remove('hidden');
  
  // Summary
  summaryText.textContent = data.summary_line || 'Audio processed successfully.';
  
  // Spectrograms
  beforeSpectrogram.src = data.before_image_url;
  afterSpectrogram.src = data.after_image_url;
  downloadSpectrogram.href = data.after_image_url;
  
  // Audio
  cleanedAudio.src = data.audio_url;
  downloadAudio.href = data.audio_url;
  downloadAudio.download = data.audio_download_name || 'cleaned_audio.wav';
  
  // Duration
  const duration = parseFloat(data.duration_seconds) || 0;
  playbackStatus.textContent = `Duration: ${duration.toFixed(2)}s`;
  
  // Segments
  const segs = (data.segments || []).map(s => ({
    start: parseFloat(s.start),
    end: parseFloat(s.end)
  }));
  renderSegments(segs, duration);
}

// Reset results
function resetResults() {
  resultsEmpty.classList.remove('hidden');
  resultsContent.classList.add('hidden');
}

// Process audio
async function processAudio() {
  if (!currentFile) return;
  
  showProcessing();
  hideError();
  resetResults();
  
  const formData = new FormData();
  formData.append('audio', currentFile);
  
  try {
    updateProgress(20, 'Generating spectrogram...');
    
    const response = await fetch(`${API_BASE}/api/clean`, {
      method: 'POST',
      body: formData
    });
    
    updateProgress(60, 'Cleaning audio...');
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Server error: ${response.status}`);
    }
    
    updateProgress(80, 'Generating results...');
    
    const data = await response.json();
    
    if (data.error) {
      throw new Error(data.error);
    }
    
    updateProgress(100, 'Complete!');
    
    // Small delay for visual feedback
    await new Promise(resolve => setTimeout(resolve, 500));
    
    displayResults(data);
    hideProcessing();
    
  } catch (error) {
    hideProcessing();
    showError(error.message || 'Failed to process audio. Make sure the backend server is running.');
    console.error('Processing error:', error);
  }
}

// Event listeners
audioInput.addEventListener('change', (e) => {
  handleFileSelect(e.target.files[0]);
});

clearFile.addEventListener('click', clearSelectedFile);

form.addEventListener('submit', (e) => {
  e.preventDefault();
  processAudio();
});

// Drag and drop
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

// Audio playback events
cleanedAudio.addEventListener('timeupdate', updatePlaybackStatus);
cleanedAudio.addEventListener('seeked', updatePlaybackStatus);
cleanedAudio.addEventListener('play', updatePlaybackStatus);
cleanedAudio.addEventListener('pause', updatePlaybackStatus);
cleanedAudio.addEventListener('loadedmetadata', () => {
  playbackStatus.textContent = `Duration: ${cleanedAudio.duration.toFixed(2)}s`;
});
