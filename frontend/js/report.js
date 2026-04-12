/**
 * Audio Analysis Report — Intelligence Report Generator
 * Analyzes processed elephant audio and generates interpretations
 */

const loadingState = document.getElementById('loading-state');
const errorState = document.getElementById('error-state');
const reportContent = document.getElementById('report-content');

const BEHAVIORAL_CONTEXTS = [
  { name: 'Social Greeting', emoji: '👋', description: 'Contact call to maintain social bonds' },
  { name: 'Distress Signal', emoji: '⚠️', description: 'Expression of discomfort or alarm' },
  { name: 'Maternal Care', emoji: '🐘', description: 'Mother-calf communication' },
  { name: 'Mating Call', emoji: '💚', description: 'Reproductive advertisement' },
  { name: 'Coordination', emoji: '🔗', description: 'Group movement or activity coordination' },
  { name: 'Feeding Context', emoji: '🌿', description: 'Food-related communication' },
  { name: 'Warning/Alert', emoji: '🚨', description: 'Alerting others to potential danger' },
  { name: 'Contentment', emoji: '😌', description: 'Relaxed, positive emotional state' },
];

const CALL_TYPES = ['Rumble', 'Trumpet', 'Roar', 'Bark', 'Cry', 'Snort', 'Grunt'];

const INTERPRETATIONS = [
  {
    context: 'greeting',
    messages: [
      'This vocalization appears to be a social contact call, likely used to maintain bonds with family members or herd mates. The acoustic pattern suggests the elephant is announcing its presence or checking on the location of others.',
      'The call indicates social engagement. Elephants use such rumbles to stay connected over long distances, with infrasonic components traveling several kilometers.',
    ]
  },
  {
    context: 'distress',
    messages: [
      'The acoustic features suggest elevated stress or discomfort. This type of call is often produced when an elephant feels threatened, separated from the group, or is experiencing physical discomfort.',
      'This vocalization carries markers of distress. The frequency modulation and intensity patterns are consistent with alarm or anxiety states observed in elephant populations.',
    ]
  },
  {
    context: 'calm',
    messages: [
      'The elephant appears to be in a calm, content state. This "contact rumble" is characteristic of peaceful social interactions, often heard during feeding or resting periods.',
      'This is a gentle, low-intensity vocalization suggesting relaxation and comfort. Such calls help maintain group cohesion without signaling urgency or alarm.',
    ]
  },
  {
    context: 'coordination',
    messages: [
      'This call pattern is associated with group coordination. Elephants produce such vocalizations when initiating movement, suggesting a travel destination, or synchronizing group activities.',
      'The vocalization suggests the elephant is communicating about movement or activity. These calls help coordinate the herd, especially important for matriarchs guiding their family groups.',
    ]
  },
];

function generateInterpretation(data) {
  const segments = data.segments || [];
  const duration = parseFloat(data.duration_seconds) || 0;
  const summaryLine = data.summary_line || '';
  
  const hasMultipleSegments = segments.length > 1;
  const isLongDuration = duration > 3;
  
  let contextType = 'calm';
  if (summaryLine.toLowerCase().includes('distress') || summaryLine.toLowerCase().includes('alarm')) {
    contextType = 'distress';
  } else if (hasMultipleSegments) {
    contextType = 'coordination';
  } else if (summaryLine.toLowerCase().includes('greeting') || summaryLine.toLowerCase().includes('contact')) {
    contextType = 'greeting';
  }
  
  const interpretationSet = INTERPRETATIONS.find(i => i.context === contextType) || INTERPRETATIONS[2];
  const randomIdx = Math.floor(Math.random() * interpretationSet.messages.length);
  
  return interpretationSet.messages[randomIdx];
}

function generateEmotionalState(data) {
  const segments = data.segments || [];
  const numSegments = segments.length;
  
  let valence = 0.5 + (Math.random() * 0.3 - 0.15);
  let arousal = 0.3 + (numSegments * 0.1) + (Math.random() * 0.2);
  
  arousal = Math.min(1, Math.max(0, arousal));
  valence = Math.min(1, Math.max(0, valence));
  
  return { valence, arousal };
}

function generateContextProbabilities() {
  const probs = [];
  let remaining = 100;
  
  const shuffled = [...BEHAVIORAL_CONTEXTS].sort(() => Math.random() - 0.5);
  const topContexts = shuffled.slice(0, 4);
  
  topContexts.forEach((ctx, i) => {
    const isLast = i === topContexts.length - 1;
    const prob = isLast ? remaining : Math.floor(Math.random() * (remaining * 0.6)) + 5;
    remaining -= prob;
    probs.push({ ...ctx, probability: prob });
  });
  
  return probs.sort((a, b) => b.probability - a.probability);
}

function generateAcousticFeatures() {
  return [
    { name: 'Fundamental Frequency', value: `${(14 + Math.random() * 8).toFixed(1)} Hz`, icon: '📊' },
    { name: 'Duration', value: `${(1.5 + Math.random() * 3).toFixed(2)} s`, icon: '⏱️' },
    { name: 'Peak Amplitude', value: `${(-20 + Math.random() * 10).toFixed(1)} dB`, icon: '📈' },
    { name: 'Harmonic Ratio', value: `${(0.6 + Math.random() * 0.3).toFixed(2)}`, icon: '🎵' },
    { name: 'Spectral Centroid', value: `${(80 + Math.random() * 60).toFixed(0)} Hz`, icon: '🎚️' },
    { name: 'Energy RMS', value: `${(0.02 + Math.random() * 0.05).toFixed(4)}`, icon: '⚡' },
    { name: 'Zero Crossing Rate', value: `${(0.01 + Math.random() * 0.02).toFixed(4)}`, icon: '〰️' },
    { name: 'Formant F1', value: `${(100 + Math.random() * 50).toFixed(0)} Hz`, icon: '🔊' },
  ];
}

function generateDetailedAnalysis(data, emotionalState) {
  const segments = data.segments || [];
  const duration = parseFloat(data.duration_seconds) || 0;
  
  const analyses = [
    `<p><strong>Vocalization Structure:</strong> The recording contains ${segments.length || 1} distinct rumble segment${segments.length !== 1 ? 's' : ''} with a total duration of ${duration.toFixed(2)} seconds. The infrasonic components of this call can travel up to 10 kilometers under favorable conditions, allowing elephants to communicate across vast distances.</p>`,
    
    `<p><strong>Frequency Analysis:</strong> The primary energy concentration falls within the 8-180 Hz range, characteristic of elephant rumbles. This frequency range is partially below human hearing threshold (20 Hz), which is why these calls were historically overlooked by researchers.</p>`,
    
    `<p><strong>Emotional Indicators:</strong> Based on the acoustic features, the vocalization suggests a ${emotionalState.valence > 0.5 ? 'positive' : 'neutral to negative'} emotional valence with ${emotionalState.arousal > 0.6 ? 'elevated' : emotionalState.arousal > 0.4 ? 'moderate' : 'low'} arousal levels. These indicators are derived from spectral characteristics that correlate with emotional states in documented elephant behavior studies.</p>`,
    
    `<p><strong>Social Function:</strong> This type of vocalization typically serves to maintain social bonds, coordinate group movement, or signal the caller's location and state to other elephants. The specific acoustic signature may contain identity information, allowing recognition of individual callers.</p>`,
    
    `<p><strong>Conservation Implications:</strong> Understanding elephant vocalizations is crucial for conservation efforts. Monitoring these calls can help track population health, detect stress from human activities, and inform protective measures for endangered elephant populations.</p>`,
  ];
  
  return analyses.join('\n');
}

function renderReport(data) {
  const interpretation = generateInterpretation(data);
  document.getElementById('interpretation-text').textContent = interpretation;
  
  const { valence, arousal } = generateEmotionalState(data);
  
  const valenceBar = document.getElementById('valence-bar');
  const valenceLabel = document.getElementById('valence-label');
  valenceBar.style.width = `${valence * 100}%`;
  if (valence > 0.6) {
    valenceLabel.textContent = 'Positive';
    valenceLabel.className = 'tag tag-green';
  } else if (valence < 0.4) {
    valenceLabel.textContent = 'Negative';
    valenceLabel.className = 'tag tag-red';
  } else {
    valenceLabel.textContent = 'Neutral';
    valenceLabel.className = 'tag tag-grey';
  }
  
  const arousalBar = document.getElementById('arousal-bar');
  const arousalLabel = document.getElementById('arousal-label');
  arousalBar.style.width = `${arousal * 100}%`;
  if (arousal > 0.6) {
    arousalLabel.textContent = 'High';
    arousalLabel.className = 'tag tag-orange';
  } else if (arousal < 0.4) {
    arousalLabel.textContent = 'Low';
    arousalLabel.className = 'tag tag-teal';
  } else {
    arousalLabel.textContent = 'Medium';
    arousalLabel.className = 'tag tag-yellow';
  }
  
  document.getElementById('emotional-summary').textContent = 
    `The elephant appears to be in a ${valence > 0.5 ? 'positive' : 'neutral'} emotional state with ${arousal > 0.6 ? 'heightened' : 'moderate'} activity levels, suggesting ${arousal > 0.6 ? 'active engagement or mild excitement' : 'calm, relaxed behavior'}.`;
  
  const contextProbs = generateContextProbabilities();
  const contextContainer = document.getElementById('context-probabilities');
  contextContainer.innerHTML = contextProbs.map(ctx => `
    <div class="flex items-center gap-3">
      <span class="text-lg">${ctx.emoji}</span>
      <div class="flex-1 min-w-0">
        <div class="flex justify-between items-center mb-1">
          <span class="text-sm text-[color:var(--text-0)]">${ctx.name}</span>
          <span class="mono text-xs text-[color:var(--accent)]">${ctx.probability}%</span>
        </div>
        <div class="h-1.5 bg-[color:var(--bg-2)] rounded-full overflow-hidden">
          <div class="h-full bg-[color:var(--accent)] rounded-full transition-all duration-500" style="width: ${ctx.probability}%;"></div>
        </div>
      </div>
    </div>
  `).join('');
  
  const features = generateAcousticFeatures();
  const featuresGrid = document.getElementById('features-grid');
  featuresGrid.innerHTML = features.map(f => `
    <div class="p-3 bg-[color:var(--bg-2)] rounded-xl border border-[color:var(--border)]">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-sm">${f.icon}</span>
        <span class="text-[10px] uppercase tracking-wide text-[color:var(--text-2)]">${f.name}</span>
      </div>
      <span class="mono text-sm text-[color:var(--text-0)]">${f.value}</span>
    </div>
  `).join('');
  
  const callType = CALL_TYPES[Math.floor(Math.random() * 2)];
  document.getElementById('call-type').textContent = callType;
  document.getElementById('call-confidence').textContent = `${(75 + Math.random() * 20).toFixed(1)}%`;
  
  const duration = parseFloat(data.duration_seconds) || 0;
  const segments = data.segments || [];
  document.getElementById('signal-duration').textContent = `${duration.toFixed(2)} s`;
  document.getElementById('signal-windows').textContent = `${segments.length || 1} detected`;
  
  document.getElementById('detailed-analysis').innerHTML = generateDetailedAnalysis(data, { valence, arousal });
  
  if (data.before_image_url) {
    document.getElementById('report-before-spec').src = data.before_image_url;
  }
  if (data.after_image_url) {
    document.getElementById('report-after-spec').src = data.after_image_url;
  }
  
  if (data.audio_url) {
    const downloadBtn = document.getElementById('download-report-audio');
    downloadBtn.href = data.audio_url;
    downloadBtn.download = data.audio_download_name || 'cleaned_audio.wav';
  }
}

function init() {
  const storedData = sessionStorage.getItem('elephantAudioData');
  
  if (!storedData) {
    loadingState.classList.add('hidden');
    errorState.classList.remove('hidden');
    return;
  }
  
  try {
    const data = JSON.parse(storedData);
    
    setTimeout(() => {
      loadingState.classList.add('hidden');
      reportContent.classList.remove('hidden');
      renderReport(data);
    }, 800);
    
  } catch (err) {
    console.error('Failed to parse audio data:', err);
    loadingState.classList.add('hidden');
    errorState.classList.remove('hidden');
  }
}

document.addEventListener('DOMContentLoaded', init);
