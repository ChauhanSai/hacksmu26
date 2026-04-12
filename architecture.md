# Web3 Biological Platform Architecture

This document describes the complete architecture for a decentralized platform for crowdsourcing and verifying biological field data (e.g., wildlife audio recordings). The platform leverages Next.js for the frontend, Solana for authentication and reputation management, and Python for backend data processing.

## 1. High-Level System Overview & Data Flow

The platform relies on a hybrid decentralized architecture, dividing responsibilities between off-chain infrastructure (for heavy lifting, search, and storage) and on-chain infrastructure (for security, consensus, and verification).

### Primary Data Flows
1. **Upload Pipeline:** 
   User submits raw audio -> Frontend uploads data directly to IPFS (via Pinata/Infura) -> IPFS returns CID -> Frontend requests user to sign a Solana transaction with the CID hash -> Transaction logged on-chain -> Off-chain backend indexes the new submission as `Pending Workflow` -> Python Worker grabs the CID, processes the audio, and saves analytics to the DB.
2. **Verification Pipeline:**
   Verified Biologist logs in (via wallet signature) -> Queries DB for `Pending` and processed files -> Reviews waveform and machine-learning predictions -> Approves the file -> Frontend prompts for Solana signature -> Biologist signs the `Verify` function on the smart contract -> On-chain event emitted -> Node.js indexer catches the event via WebSocket -> Updates DB to `Expert Verified`.

---

## 2. Frontend Application

**Core Framework:** Next.js (App Router), React 18, TypeScript.
**Styling & UI:** Vanilla CSS (CSS Modules) for a premium, tailored aesthetic. `framer-motion` for fluid micro-animations and page transitions without heavy CSS frameworks.
**State & Data:** `zustand` for lightweight global state (wallet status, user roles), `@tanstack/react-query` for server-state caching and DB queries.
**Web3 Stack:** `@solana/web3.js`, `@solana/wallet-adapter-react` (supports Phantom, Solflare), `@coral-xyz/anchor` for smart contract interactions.

### A. Landing Page (`/`)
*   **Technologies:** CSS Animations, Intersection Observers for scroll-reveal.
*   **Data:** Fetches aggregated platform statistics (Total Verifications, Active Biologists) via public API endpoints.
*   **Interactions:** Call-to-action buttons directly invoking the Wallet Adapter connection modal.

### B. Open Source Contributions / Explorer (`/explore`)
*   **Technologies:** `wavesurfer.js` for rendering interactive acoustic waveforms in the browser directly from IPFS streams.
*   **Flow:** Sends filtered queries to the Backend API (e.g., "Species: Elephant, Status: Verified"). Real-time pagination handled by React Query.
*   **Features:** Integrated audio player allowing users to scrub through field recordings while viewing the frequency spectrogram.

### C. Upload Portal (`/upload`)
*   **Technologies:** `react-dropzone` for drag-and-drop file ingestion, `ipfs-http-client` for browser-to-IPFS direct chunking.
*   **Flow:** 
    1. Browser slices large files to prevent RAM exhaustion.
    2. Uploads to Pinata IPFS Gateway -> Receives CID.
    3. User fills out EXIF/Metadata (GPS, Weather, Suspected Species).
    4. Triggers Solana `submitData(CID)` via Anchor client, passing the IPFS address into the blockchain.

### D. Biologist Verification Portal (`/verify`)
*   **Technologies:** Advanced Canvas/WebGL spectrogram renderers. Role-based route protection in Next.js middleware (requires verified JWT).
*   **Flow:** Displays Python worker's pre-processed data (e.g., "Worker flags potential elephant trumpet at 00:15"). The biologist reviews, then the frontend utilizes the Wallet Adapter to sign an on-chain transaction confirming the species and validity of the upload.

---

## 3. Backend & API Services

**Core Framework:** Node.js, Express (or Next.js API Routes), Prisma ORM, PostgreSQL.

### A. Application API (`api.biochain.io`)
*   **Role:** Handles all relational queries bridging the frontend to PostgreSQL, enabling fast searches over the metadata without indexing the entire blockchain.
*   **Libraries:** `prisma` (Type-safe DB interactions), `express`, `cors`, `helmet`.
*   **Core DB Schema (PostgreSQL):** 
    *   `User`: Wallet Address, Role (Contributor/Biologist), Reputation Score.
    *   `Upload`: CID, Uploader Address, Metadata (JSON coordinates, timestamp), Verification Status.
    *   `Verification`: Reviewer Address, Upload CID, Timestamp, Validator Notes.

### B. Authentication Middleware (`auth_middleware.js`)
*   **Flow:** Users do not use passwords. They sign a standardized message (`"Sign into BioChain: [Nonce]"`) with their Solana wallet.
*   **Libraries:** `tweetnacl` (Verifies ed25519 cryptographic signatures), `jsonwebtoken` (Issues a standard session JWT upon successful signature validation).

### C. On-Chain Event Indexer (`solana_indexer.js`)
*   **Role:** The bridge between the blockchain state and the fast SQL database.
*   **Libraries:** `@solana/web3.js` (RPC WebSockets).
*   **Flow:** Subscribes to `logsSubscribe` via Solana RPC. When the smart contract emits a `VerificationEvent`, it parses the transaction logs and runs an `UPDATE Uploads SET status = 'verified'` via Prisma ORM, keeping the web UI incredibly fast.

---

## 4. Python Data Processing Workers

**Core Framework:** Python 3.10+, Celery (Task Queue), Redis (Message Broker).

### Audio Analysis & Cleaning Worker (`worker.py`)
*   **Libraries:** 
    *   `librosa`, `scipy.signal`, `sklearn.decomposition`: Core libraries for STFT, filtering, and Non-Negative Matrix Factorization (NMF).
    *   `pydub`: Formatting and slicing massive field recordings into manageable chronological chunks.
    *   `torch` / `transformers`: For running inference using BioCPPNet-style U-Net architectures and AST (Audio Spectrogram Transformer) models.
*   **Data Flow & Advanced Denoising Pipeline:**
    1. **Ingestion & STFT:** Celery receives a `CID` from the Node backend, downloads the raw `.wav` from IPFS, and converts it into a complex time-frequency representation via Short-Time Fourier Transform (STFT) using a Hann window (nfft=1024, hop=200).
    2. **Classical DSP Denoising:** Applies a log-frequency axis transformation to linearize harmonics, followed by Spectral Subtraction (to remove stationary noise like generators), Wiener Filtering, and NMF (to separate tonal vehicle noise). 
    3. **Deep Learning Source Separation:** Routes the spectrogram through a trained BioCPPNet-style 2D U-Net to output distinct separation masks, effectively isolating elephant calls from environmental noise.
    4. **Frame-Level AST Verification:** Runs the separated audio through an Audio Spectrogram Transformer (AST) to verify and properly endpoint the exact temporal boundaries of the elephant rumbles.
    5. **Waveform Reconstruction:** Reconstructs the time-domain waveform using an Inverse STFT (iSTFT), strictly prioritizing phase consistency to preserve the acoustic properties of the vocalizations.
    6. **Final Band-Pass Filtering:** Applies an 8–180 Hz band-pass Butterworth filter to eliminate residual high-frequency artifacts while retaining the core fundamental frequencies (8–34 Hz) of African forest elephant rumbles.
    7. **Finalization:** Generates an image (`.png`) of the cleaned audio spectrogram, uploads it to IPFS, and POSTs a webhook back to the Node API with the extracted metrics, marking the record as `Ready for Human Review`.

---

## 5. Smart Contracts (Solana Programs)

**Core Framework:** Rust, Anchor Framework.

### `bio_reputation` Program
*   **Data Structures (PDAs - Program Derived Addresses):**
    *   `UserAccount PDA`: Seeded deterministically by `["user", wallet_pubkey]`. Stores total reputation and permission level role flags `u8` (0=Standard, 1=Verified Biologist).
    *   `UploadRecord PDA`: Seeded by `["upload", CID_hash]`. Stores the submitter's pubkey, a globally verified boolean flag, and a vector list of verifying biologist pubkeys to prevent duplicate votes.
*   **Core Instructions:**
    *   `register_user`: Initializes standard user states on-chain.
    *   `submit_file`: Initializes an `UploadRecord` PDA mapping tracking logic to an IPFS CID.
    *   `verify_file`: A constrained function that *only* executioners mathematically verified to have `role == 1` can securely call. It updates the `UploadRecord` and mints SPL Tokens (using the `spl-token` crate) as a bounty reward directly into the data contributor's and expert verifier's wallets.
