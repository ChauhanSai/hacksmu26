# Tusk 'n Tidy 🐘

**Decentralized wildlife intelligence, verified by experts.**

### 🏆 First place submission to [Hack SMU 2026](https://devpost.com/software/tusk-n-tidy)

Tusk 'n Tidy is the world's first **smart audio library** that cleans up noisy jungle recordings to let experts verify and translate what animals are actually saying: a Web3-powered platform that lets anyone **upload, analyze, and verify** elephant field data with **research-backed audio processing** and on-chain trust. 

---

## 🌎 Social Impact

Language and conservation efforts rely on accurate elephant audio data, but today, that data is often **fragmented, unverifiable, or inaccessible**. Biologists and citizen scientists collect valuable recordings, yet trust and validation remain bottlenecks.  

Tusk ’n Tidy ensures that every contribution is traceable, verified, and rewarded, empowering:
 - 🌿 Citizen scientists to contribute meaningful data
 - 🧪 Biologists to validate findings with confidence
 - 🌍 Researchers to make **elephant emotion-driven** decisions

---

## 🧠 Inspiration

Wildlife research is powerful but messy:

> “How do we know this recording is real?”
> “Where did this data come from?”
> “Whats happening in this audio?”

We wanted to build a system where every piece of data has proof, provenance, and expert validation.

To do this, we developed the world's largest and most navigable dataset of **clean, labeled elephant field recordings** covering **29 contexts** and **91 actions** with a total of **5,510** audio samples with datapoints. 

---

## 💡 What it does

* 🧹 **Multi-Stage Audio Cleaning:** Combines classical DSP (spectral subtraction, Wiener filtering, NMF) to produce clean, research-grade audio signals. See our dataflow below:

```
RAW NOISY WAV FILE
    │
    ▼
 [1. PAPER IMPLEMENTATION] 
 [pubs.aip](https://pubs.aip.org/asa/jasa/article/141/4/2715/1059147/Automated-detection-of-low-frequency-rumbles-of) 
 STFT with nfft=1024, hop=200, Hann window
    │ (Complex spectrogram: magnitude + phase)
    ▼
 [2. PAPER IMPLEMENTATION] 
 [arxiv](https://arxiv.org/abs/2410.12082) 
 Log-frequency axis transformation
    │ (Makes harmonic structure linear)
    ▼
 [3. PAPER IMPLEMENTATION] 
 [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC8648737/) 
 SPECTRAL SUBTRACTION (α=1.5, β=0.02)
    │ (Removes stationary noise: generator hum)
    ▼
[4] WIENER FILTERING
    │ (Smooths noise removal, reduces musical noise)
    ▼
[5] NMF SEPARATION
    │ (Removes tonal components: car engine, generator RPM)
    ▼
[6] U-NET MASK PREDICTION (BioCPPNet architecture)
    │ (Deep learning source separation)
    │ Outputs: mask_elephant, mask_noise
    ▼
[7] APPLY MASK: Sxx_elephant = Sxx_noisy × mask_elephant
    │
    ▼
[8] AST FRAME-LEVEL VERIFICATION (arXiv 2410.12082)
    │ (Detects exact rumble boundaries, removes non-elephant frames)
    │
    ▼
[9] INVERSE STFT → Time-domain waveform
    │ (nfft=1024, hop=200, Hann window)
    │
    ▼
[10] BAND-PASS FILTER: 8–180 Hz
    │ (Removes any residual high-freq noise, DC offset
    │
    ▼
CLEAN ELEPHANT AUDIO RECORDING
```

--- 

* 🧠 **Research-backed Audio Processing:** Filter recordings using research pipelines to detect and isolate animal motivations and thinking.
* 🎤 **LIVE Monitoring:** Capture audio in real time and instantly run cleaning, detection, and labeling—surfacing elephant calls with live spectrograms and on-the-fly annotations for immediate insight.
* 🌍 **Decentralized Uploads:** Users upload raw field recordings directly to IPFS, ensuring permanent, tamper-proof storage.
* 🧪 **Expert Verification:** Verified biologists review uploads, cleaning, and labels and confirm findings via blockchain-backed approvals.
* 📊 **Interactive Explorer:** Browse recordings, view spectrograms, and analyze elephant audio in real time.

---

## 🌟 ML-powered Emotion Analysis

* **Behavioral context:** Each call is framed as multi-class prediction over ethogram-style contexts (e.g. affiliative, protest & distress, social play, movement & leadership), backed by a high-accuracy acoustic classifier on a 256-D fingerprint.
* **Valence & arousal:** The linguistics pipeline also learns coarse valence (positive / neutral / negative) and arousal (low / medium / high) from conttext, used for emotion summaries.
* **Interpretation cards:** Fuse cluster ID, predicted context, confidence language, and valence/arousal tags so reviewers can spot-check stories call-by-call.

## 🎯 Acoustic fingerprint & context classifier

* **Input representation:** 256 dimensions of elephant-specific features grouped into rumble-band energy, ~7.7 Hz tremor, temporal phases (onset / body / offset), and timbre (MFCCs + mel statistics), roughly a voice print for infrasonic calls.
* **Model family (dashboard narrative):** LightGBM-style gradient boosting on tabular acoustics (91.6% accuracy on evaluation).

## 🔮 KNN Behavior Analysis

* **KNN:** KNN uses five audios with the smallest absolute duration gap to the cleaned recording, then overlays them on the same UMAP, visualizing biological differences in duration connection versus emotion connection.
* **Link to behavior:** UMAP clusters acoustic clusters to dominant behavioral contexts.

---

## 🌟 Key Benefits

* **Open Science:** Anyone can explore and contribute to global biodiversity data.
* **Live Field Recordings:** Analyze elephant emotions and actions using audio in real-time.

---

## 🚀 Use Cases

* Wildlife researchers collecting and validating animal recordings
* Conservation organizations tracking endangered species
* Citizen scientists contributing field data globally
* Academic institutions building open-access biological datasets
* LIVE environmental monitoring using audio-based species detection

---

## ☀️ Solana Integration for Open Science

Our Web3 Stack is as follows:
* Solana Web3.js for blockchain interaction
* Wallet authentication via Phantom/Solflare
* Anchor Framework for smart contracts

What Solana Does in Our System
* 🧾 Proof of Origin: Every audio upload is tied to a wallet signature and stored on-chain as a CID reference, creating a permanent, tamper-proof record of who submitted what.
* 🧪 Expert Verification as a Transaction: When a biologist approves a recording, it’s not just a UI action, it’s a verification event.
* 🏅 Reputation System: Users build credibility through verified contributions, stored transparently and resistant to manipulation.
* 🪙 Incentive Alignment: Smart contracts reward both contributors and validators, ensuring high-quality data and honest reviews.
* 🔄 Real-Time Sync: A WebSocket indexer listens to on-chain events and updates the app instantly—bridging blockchain and a fast user experience.

Heavy data stored on IPFS **+** Trust/verification stored on Solana **=** efficient + scalable + verifiable

---

## 🛠️ How we built it

**Frontend**  
* HTML, Tailwind CSS, JavaScript
* Plotly.js for in-browser waveform visualization

**Backend & APIs**
* Python + Flask
* Audio / DSP: librosa, scipy, soundfile, matplotlib

**AIs & Data Processing**  
* **Audio pipeline:** STFT + spectral denoising, U-Net source separation
* **Python:** librosa, scipy, scikit-learn
* **Gemini API:** Lightweight quiz and answer-card synthesis, grounded to the retrieved transcript span.  
* **Google Cloud Text-to-Speech:** Reads back care instructions in a clear, natural voice.

**Media & Data**  
* **Custom largest dataset:** **5,510+** segmented elephant field recordings covering **29 contexts** and **91 actions.**

---

## 🚧 Challenges we overcame

* Handling large audio uploads with **efficient browser chunking** + IPFS storage
* Designing a robust **non-AI processing pipeline** and bridging it with AI for noisy real-world field recordings
* Creating a UX that balances scientific depth with accessibility

---

## 🏆 Accomplishments

* **End-to-End Pipeline:** Upload → IPFS → Research-backed processing → expert verification → on-chain record
* **AI-Powered Bioacoustics:** Accurate emotion analyzer of wildlife sounds
* **Decentralized Trust Layer:** Every contribution backed by verifiable blockchain transactions
* **Interactive Explorer:** Real-time browsing of verified biological data
* **Incentive System:** Contributors and experts rewarded fairly via smart contracts

---

## 📚 What we learned

* Real-world data (like wildlife audio) is messy, and signal processing matters
* UX is critical, even in technical platforms, to drive adoption for biologists

---

## 🚀 Next Steps

* Build a mobile field recording app for phones for easier data collection
* Add DAO governance for community-driven validation standards
* Integrate with global biodiversity databases (e.g., GBIF)
* Introduce real-time alerts for species safety concerns

---

## ❤️ Why Tusk 'n Tidy

Tusk ’n Tidy transforms biological data into a **trusted knowledge network.** We’re cleaning the noise, proving the truth, and protecting the giants. 

Let’s change conservation together, **one recording at a time!** 🏞️
