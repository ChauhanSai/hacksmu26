/**
 * Contribute page: session bar, tab reset, mock + real biologist queue.
 */

const API = "";

/** Reference queue items merged with live API data when ids don’t collide. */
const MOCK_SUBMISSIONS = [
  {
    id: "mock-001",
    wallet: "7xKX…mPqR",
    note: "Zoom H5, light wind.",
    sex: "female",
    age: "Adult",
    ethogramContext: "Advertisement & Attraction",
    ethogramName: "Estrous-Rumble",
    recordingMode: "acoustic-vocal",
    situation: "Forest clearing at dawn; elephants moving through trees ~40 m.",
    duration: "1 – 3 minutes",
    soundSegments: "0:00–0:35 low-frequency rumble; 0:35–1:10 contact calls; 1:10–2:10 footsteps & brush",
    status: "pending",
    isMock: true,
  },
  {
    id: "mock-002",
    wallet: "9AbC…vWxY",
    note: "",
    sex: "female",
    age: "Adult",
    ethogramContext: "Affiliative",
    ethogramName: "Greeting-Rumble",
    recordingMode: "acoustic-vocal",
    situation: "Dry-season savannah; herd spread across shallow basin.",
    duration: "30 seconds – 1 minute",
    soundSegments: "0:00–0:20 sustained rumble; 0:20–0:48 distant trumpet",
    status: "pending",
    isMock: true,
  },
  {
    id: "mock-003",
    wallet: "1111…1111",
    note: "Hydrophone rig",
    sex: "unknown",
    age: "Juvenile/Adolescent",
    ethogramContext: "Ambivalent",
    ethogramName: "Nasal-Trumpet",
    recordingMode: "acoustic-vocal",
    situation: "River ford; hydrophone 0.5 m below surface, current light.",
    duration: "Over 5 minutes",
    soundSegments: "0:00–1:00 sloshing + low pulses; 1:00–3:00 intermittent bubbles",
    status: "pending",
    isMock: true,
  },
  {
    id: "mock-004",
    wallet: "2222…2222",
    note: "",
    sex: "male",
    age: "Adult",
    ethogramContext: "Aggressive",
    ethogramName: "Roar",
    recordingMode: "acoustic-vocal",
    situation: "Night; open woodland, insects loud in foreground.",
    duration: "1 – 3 minutes",
    soundSegments: "0:00–0:30 insect bed; 0:30–1:05 single long rumble crescendo",
    status: "pending",
    isMock: true,
  },
  {
    id: "mock-005",
    wallet: "3333…3333",
    note: "Calibration clip",
    sex: "unknown",
    age: "Adult",
    ethogramContext: "Attacking & Mobbing",
    ethogramName: "Charge",
    recordingMode: "acoustic-vocal",
    situation: "Controlled test: static mic, known distance to speaker.",
    duration: "Under 30 seconds",
    soundSegments: "0:00–0:15 tone + short rumble sample",
    status: "pending",
    isMock: true,
  },
  {
    id: "mock-006",
    wallet: "4444…4444",
    note: "",
    sex: "female",
    age: "Estrous",
    ethogramContext: "Advertisement & Attraction",
    ethogramName: "Estrous-Roar",
    recordingMode: "acoustic-vocal",
    situation: "Short field sanity check before longer session.",
    duration: "30 seconds – 1 minute",
    soundSegments: "0:00–0:22 ambient + one trumpet",
    status: "pending",
    isMock: true,
  },
];

/** @type {Record<string, "accepted" | "rejected">} */
let mockReviewState = {};

/** @type {Record<string, object>} */
let submissionDetailCache = {};

function getProvider() {
  if (typeof window === "undefined") return null;
  if (window.solana?.isPhantom) return window.solana;
  if (window.phantom?.solana) return window.phantom.solana;
  return window.solana || null;
}

async function fetchJson(path, opts = {}) {
  const r = await fetch(`${API}${path}`, {
    credentials: "include",
    ...opts,
    headers: { ...(opts.headers || {}) },
  });
  const text = await r.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!r.ok) {
    const err = new Error(data?.error || data?.message || r.statusText || "Request failed");
    err.status = r.status;
    err.body = data;
    throw err;
  }
  return data;
}

function explorerTxUrl(sig, cluster) {
  const c = cluster === "mainnet-beta" ? "" : `?cluster=${encodeURIComponent(cluster || "devnet")}`;
  return `https://explorer.solana.com/tx/${sig}${c}`;
}

function explorerAddressUrl(pubkey, cluster) {
  const c = cluster === "mainnet-beta" ? "" : `?cluster=${encodeURIComponent(cluster || "devnet")}`;
  return `https://explorer.solana.com/address/${pubkey}${c}`;
}

/** Normalize wallet `signAndSendTransaction` / similar return values to a base58 signature string. */
async function normalizeWalletSignature(result) {
  if (result == null) {
    throw new Error("Wallet returned no signature.");
  }
  if (typeof result === "string") {
    return result;
  }
  const raw = result.signature ?? result.txid ?? result;
  if (typeof raw === "string") {
    return raw;
  }
  if (raw instanceof Uint8Array) {
    const { encode } = await import("https://esm.sh/bs58@5.0.0");
    return encode(raw);
  }
  if (Array.isArray(raw)) {
    const { encode } = await import("https://esm.sh/bs58@5.0.0");
    return encode(Uint8Array.from(raw));
  }
  throw new Error("Could not read transaction signature from wallet. Approve in Phantom and try again.");
}

/**
 * Send SOL from the biologist's Phantom wallet to the contributor (submitter).
 * User must approve the transaction in Phantom; use Solana **devnet** in Phantom settings.
 */
async function sendRewardFromBiologistWallet({ fromPubkey, toWallet, lamports }) {
  const { Connection, Transaction, SystemProgram, PublicKey } = await import(
    "https://esm.sh/@solana/web3.js@1.95.4"
  );
  const rpc = config.rpcUrl || "https://api.devnet.solana.com";
  const connection = new Connection(rpc, "confirmed");
  const from = new PublicKey(fromPubkey);
  const to = new PublicKey(toWallet);
  const lam = Math.floor(Number(lamports));
  if (!Number.isFinite(lam) || lam <= 0) {
    throw new Error("Invalid reward amount.");
  }
  const tx = new Transaction().add(
    SystemProgram.transfer({
      fromPubkey: from,
      toPubkey: to,
      lamports: lam,
    })
  );
  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("finalized");
  tx.recentBlockhash = blockhash;
  tx.feePayer = from;
  const provider = getProvider();
  if (!provider) {
    throw new Error("Install Phantom and connect your biologist wallet.");
  }

  const sendOpts = { skipPreflight: false, maxRetries: 5, preflightCommitment: "confirmed" };

  let sig;

  if (typeof provider.signAndSendTransaction === "function") {
    let result;
    try {
      result = await provider.signAndSendTransaction(tx, sendOpts);
    } catch (e1) {
      try {
        result = await provider.signAndSendTransaction(tx);
      } catch (e2) {
        const msg = e2?.message || e1?.message || "signAndSendTransaction failed";
        throw new Error(
          `${msg} — ensure Phantom is on **Devnet** (Settings → Developer Settings) and try again.`
        );
      }
    }
    sig = await normalizeWalletSignature(result);
  } else if (typeof provider.signTransaction === "function") {
    const signed = await provider.signTransaction(tx);
    sig = await connection.sendRawTransaction(signed.serialize(), sendOpts);
  } else {
    throw new Error("This wallet cannot sign Solana transactions. Use Phantom.");
  }

  try {
    await connection.confirmTransaction(
      { signature: sig, blockhash, lastValidBlockHeight },
      "confirmed"
    );
  } catch {
    const status = await connection.getSignatureStatus(sig);
    if (status?.value?.confirmationStatus) {
      return sig;
    }
    throw new Error(
      "Transaction submitted but confirmation timed out. Check Solana Explorer for this signature, or retry if it did not land."
    );
  }
  return sig;
}

/**
 * After tab switch or first load: disconnect already ran — prompt Phantom so you can pick Contributor vs Biologist wallet.
 */
async function promptPhantomConnectForRole() {
  const p = getProvider();
  if (!p) {
    if (activeTab === "contributor") phantomHint.classList.remove("hidden");
    if (activeTab === "biologist" && bioPhantomHint) bioPhantomHint.classList.remove("hidden");
    updateSessionBar();
    updateRoleHint();
    return;
  }
  if (phantomHint) phantomHint.classList.add("hidden");
  if (bioPhantomHint) bioPhantomHint.classList.add("hidden");
  try {
    await p.connect();
    const pk = p.publicKey?.toBase58?.();
    if (!pk) return;
    if (activeTab === "contributor") {
      showWalletUi(true, pk);
      await refreshWalletStatsForPubkey(pk);
      startBalancePolling(pk);
    } else if (activeTab === "biologist" && biologistLoggedIn) {
      showBioWalletUi(true, pk);
      await refreshWalletStatsForPubkey(pk);
      startBalancePolling(pk);
    }
  } catch {
    /* user dismissed Phantom */
  }
  updateSessionBar();
  updateRoleHint();
}

async function syncBioWalletAfterLogin() {
  if (!biologistLoggedIn) return;
  const pk = getConnectedPubkeySync();
  if (pk) {
    showBioWalletUi(true, pk);
    await refreshWalletStatsForPubkey(pk);
    startBalancePolling(pk);
  }
}

function pkShort(pk) {
  const s = (pk || "").trim();
  if (!s) return "—";
  return s.length > 12 ? `${s.slice(0, 4)}…${s.slice(-4)}` : s;
}

// --- DOM ---
const tabContributor = document.getElementById("tab-contributor");
const tabBiologist = document.getElementById("tab-biologist");
const panelContributor = document.getElementById("panel-contributor");
const panelBiologist = document.getElementById("panel-biologist");
const rewardSolEl = document.getElementById("reward-sol");
const rewardMetaEl = document.getElementById("reward-meta");
const roleSwitchHint = document.getElementById("role-switch-hint");
const roleSwitchHintText = document.getElementById("role-switch-hint-text");
const roleSwitchHintDismiss = document.getElementById("role-switch-hint-dismiss");

const sessionRolePill = document.getElementById("session-role-pill");
const sessionWalletLine = document.getElementById("session-wallet-line");
const sessionWalletBtn = document.getElementById("session-wallet-btn");
const sessionBioCluster = document.getElementById("session-bio-cluster");
const sessionBioLine = document.getElementById("session-bio-line");
const sessionBioBtn = document.getElementById("session-bio-btn");

const walletNone = document.getElementById("wallet-none");
const walletConnected = document.getElementById("wallet-connected");
const btnConnect = document.getElementById("btn-connect");
const btnDisconnect = document.getElementById("btn-disconnect");
const phantomHint = document.getElementById("phantom-hint");
const walletPubkey = document.getElementById("wallet-pubkey");
const contribFile = document.getElementById("contrib-file");
const contribNote = document.getElementById("contrib-note");
const btnSubmit = document.getElementById("btn-submit");
const contribMsg = document.getElementById("contrib-msg");

const bioAfterLogin = document.getElementById("bio-after-login");
const bioWalletNone = document.getElementById("bio-wallet-none");
const bioWalletConnected = document.getElementById("bio-wallet-connected");
const btnBioConnect = document.getElementById("btn-bio-connect");
const btnBioDisconnect = document.getElementById("btn-bio-disconnect");
const bioPhantomHint = document.getElementById("bio-phantom-hint");
const bioWalletPubkey = document.getElementById("bio-wallet-pubkey");

const bioLoginWrap = document.getElementById("bio-login-wrap");
const bioDashboard = document.getElementById("bio-dashboard");
const bioUsername = document.getElementById("bio-username");
const bioPassword = document.getElementById("bio-password");
const bioUserLabel = document.getElementById("bio-user-label");
const bioLoginBtn = document.getElementById("bio-login-btn");
const bioLoginMsg = document.getElementById("bio-login-msg");
const bioLogoutBtn = document.getElementById("bio-logout-btn");
const bioList = document.getElementById("bio-list");
const bioEmpty = document.getElementById("bio-empty");

const submissionModal = document.getElementById("submission-detail-modal");
const submissionModalBackdrop = document.getElementById("submission-modal-backdrop");
const submissionModalClose = document.getElementById("submission-modal-close");
const modalSubId = document.getElementById("modal-sub-id");
const modalSubBadge = document.getElementById("modal-sub-badge");
const modalMetaEthogramContext = document.getElementById("modal-meta-ethogram-context");
const modalMetaEthogramName = document.getElementById("modal-meta-ethogram-name");
const modalMetaSex = document.getElementById("modal-meta-sex");
const modalMetaAge = document.getElementById("modal-meta-age");
const modalMetaMode = document.getElementById("modal-meta-mode");
const modalMetaDuration = document.getElementById("modal-meta-duration");
const modalMetaSituation = document.getElementById("modal-meta-situation");
const modalMetaSounds = document.getElementById("modal-meta-sounds");
const modalMetaWallet = document.getElementById("modal-meta-wallet");
const modalMetaNoteWrap = document.getElementById("modal-meta-note-wrap");
const modalMetaNote = document.getElementById("modal-meta-note");
const modalAudioWrap = document.getElementById("modal-audio-wrap");
const modalAudio = document.getElementById("modal-audio");
const modalNoAudio = document.getElementById("modal-no-audio");
const modalActions = document.getElementById("modal-actions");
const modalBtnAccept = document.getElementById("modal-btn-accept");
const modalBtnReject = document.getElementById("modal-btn-reject");

const acceptCelebrationRoot = document.getElementById("accept-celebration-root");
const acceptCelebrationTitle = document.getElementById("accept-celebration-title");
const acceptCelebrationSub = document.getElementById("accept-celebration-sub");
const acceptCelebrationExplorer = document.getElementById("accept-celebration-explorer");
const acceptCelebrationDismiss = document.getElementById("accept-celebration-dismiss");

const metaEthogramContext = document.getElementById("meta-ethogram-context");
const metaEthogramName = document.getElementById("meta-ethogram-name");
const metaGender = document.getElementById("meta-gender");
const metaAge = document.getElementById("meta-age");
const metaMode = document.getElementById("meta-mode");
const metaSituation = document.getElementById("meta-situation");
const metaDuration = document.getElementById("meta-duration");
const metaDurationOther = document.getElementById("meta-duration-other");
const metaSounds = document.getElementById("meta-sounds");

/** @type {null | { contextToNames: Record<string, string[]>, contexts: string[], ages: string[], genders: string[], modes: string[], allNames: string[] }} */
let ethogramOptions = null;

/** Default 1.5 SOL reward if config API fails (matches server `REWARD_LAMPORTS` default). */
const DEFAULT_REWARD_LAMPORTS = 1_500_000_000;

let config = { rewardSol: 0, network: "devnet", treasuryConfigured: false, rpcUrl: "" };
let biologistLoggedIn = false;
/** @type {"contributor"|"biologist"} */
let activeTab = "contributor";
let balancePollTimer = null;
let roleHintDismissed = false;

function setTab(which) {
  const isContrib = which === "contributor";
  tabContributor.classList.toggle("bg-[color:var(--accent-glow)]", isContrib);
  tabContributor.classList.toggle("text-[color:var(--accent)]", isContrib);
  tabContributor.classList.toggle("border", isContrib);
  tabContributor.classList.toggle("border-[color:var(--accent-dim)]", isContrib);
  tabContributor.classList.toggle("text-[color:var(--text-2)]", !isContrib);
  tabBiologist.classList.toggle("bg-[color:var(--accent-glow)]", !isContrib);
  tabBiologist.classList.toggle("text-[color:var(--accent)]", !isContrib);
  tabBiologist.classList.toggle("border", !isContrib);
  tabBiologist.classList.toggle("border-[color:var(--accent-dim)]", !isContrib);
  tabBiologist.classList.toggle("text-[color:var(--text-2)]", isContrib);
  panelContributor.classList.toggle("hidden", !isContrib);
  panelBiologist.classList.toggle("hidden", isContrib);
  if (sessionBioCluster) {
    if (isContrib) {
      sessionBioCluster.classList.add("hidden");
      sessionBioCluster.classList.remove("flex");
    } else {
      sessionBioCluster.classList.remove("hidden");
      sessionBioCluster.classList.add("flex");
    }
  }
}

function stopBalancePolling() {
  if (balancePollTimer) {
    clearInterval(balancePollTimer);
    balancePollTimer = null;
  }
}

function clearWalletStats(prefix) {
  const sol = document.getElementById(`stat-${prefix}-sol`);
  const lam = document.getElementById(`stat-${prefix}-lamports`);
  const net = document.getElementById(`stat-${prefix}-network`);
  const upd = document.getElementById(`stat-${prefix}-updated`);
  const ex = document.getElementById(`stat-${prefix}-explorer`);
  if (sol) sol.textContent = "—";
  if (lam) lam.textContent = "— lamports";
  if (net) net.textContent = "devnet";
  if (upd) upd.textContent = "—";
  if (ex) {
    ex.classList.add("hidden");
    ex.href = "#";
  }
}

async function fetchWalletBalance(pubkey) {
  return fetchJson(`/api/contribute/wallet/${encodeURIComponent(pubkey)}/balance`);
}

function applyWalletStats(prefix, pubkey, data) {
  const sol = document.getElementById(`stat-${prefix}-sol`);
  const lam = document.getElementById(`stat-${prefix}-lamports`);
  const net = document.getElementById(`stat-${prefix}-network`);
  const upd = document.getElementById(`stat-${prefix}-updated`);
  const ex = document.getElementById(`stat-${prefix}-explorer`);
  const cluster = data.network || config.network || "devnet";
  if (sol) sol.textContent = `${Number(data.sol).toFixed(6)} SOL`;
  if (lam) lam.textContent = `${data.lamports?.toLocaleString?.() ?? data.lamports} lamports`;
  if (net) net.textContent = cluster;
  if (upd) upd.textContent = new Date().toLocaleTimeString();
  if (ex && pubkey) {
    ex.href = explorerAddressUrl(pubkey, cluster);
    ex.classList.remove("hidden");
  }
}

async function refreshWalletStatsForPubkey(pubkey) {
  if (!pubkey) return;
  try {
    const data = await fetchWalletBalance(pubkey);
    applyWalletStats("contrib", pubkey, data);
    applyWalletStats("bio", pubkey, data);
  } catch {
    clearWalletStats("contrib");
    clearWalletStats("bio");
  }
}

function startBalancePolling(pubkey) {
  stopBalancePolling();
  balancePollTimer = setInterval(() => {
    refreshWalletStatsForPubkey(pubkey);
  }, 12000);
}

async function resetAllSessions() {
  stopBalancePolling();
  mockReviewState = {};
  roleHintDismissed = false;
  try {
    await fetchJson("/api/contribute/biologist/logout", { method: "POST" });
  } catch {
    /* ignore */
  }
  const p = getProvider();
  try {
    if (p?.disconnect) await p.disconnect();
  } catch {
    /* ignore */
  }
  biologistLoggedIn = false;
  if (bioUserLabel) bioUserLabel.textContent = "";
  if (bioLoginWrap) bioLoginWrap.classList.remove("hidden");
  if (bioAfterLogin) bioAfterLogin.classList.add("hidden");
  if (bioList) bioList.innerHTML = "";
  showWalletUi(false);
  showBioWalletUi(false);
  clearWalletStats("contrib");
  clearWalletStats("bio");
  updateSessionBar();
}

function showWalletUi(connected, pubkeyStr) {
  walletNone.classList.toggle("hidden", connected);
  walletConnected.classList.toggle("hidden", !connected);
  if (connected && pubkeyStr) {
    walletPubkey.textContent = pubkeyStr;
  }
}

function showBioWalletUi(connected, pubkeyStr) {
  if (!bioWalletNone || !bioWalletConnected || !bioWalletPubkey) return;
  bioWalletNone.classList.toggle("hidden", connected);
  bioWalletConnected.classList.toggle("hidden", !connected);
  if (connected && pubkeyStr) {
    bioWalletPubkey.textContent = pubkeyStr;
  }
}

function setContribMsg(text, kind) {
  const base = "text-sm sm:text-base font-medium min-h-[1.5rem]";
  const tone =
    kind === "ok"
      ? " text-[color:var(--risk-low)]"
      : kind === "err"
        ? " text-[color:var(--risk-crit)]"
        : " text-[color:var(--text-1)]";
  contribMsg.textContent = text;
  contribMsg.className = base + tone;
}

async function ensureWalletPubkey() {
  const p = getProvider();
  if (!p) return null;
  try {
    await p.connect({ onlyIfTrusted: true });
  } catch {
    /* not trusted */
  }
  let pk = p.publicKey?.toBase58?.();
  if (!pk) {
    try {
      await p.connect();
      pk = p.publicKey?.toBase58?.();
    } catch {
      return null;
    }
  }
  return pk || null;
}

function getConnectedPubkeySync() {
  const p = getProvider();
  return p?.publicKey?.toBase58?.() || null;
}

function updateSessionBar() {
  const pk = getConnectedPubkeySync();
  if (sessionRolePill) sessionRolePill.textContent = activeTab === "contributor" ? "Contributor" : "Biologist";
  if (sessionWalletLine) {
    sessionWalletLine.textContent = pk ? `Wallet ${pkShort(pk)}` : "Wallet — not connected";
  }
  if (sessionWalletBtn) {
    sessionWalletBtn.textContent = pk ? "Disconnect" : "Connect";
  }
  if (sessionBioLine && activeTab === "biologist") {
    if (biologistLoggedIn) {
      const u = (bioUserLabel?.textContent || "").replace(/^Signed in as\s+/i, "").trim();
      sessionBioLine.textContent = u ? `Bio · ${u}` : "Bio · signed in";
    } else {
      sessionBioLine.textContent = "Bio · not signed in";
    }
  }
  if (sessionBioBtn) {
    const show = activeTab === "biologist" && biologistLoggedIn;
    sessionBioBtn.classList.toggle("hidden", !show);
  }
}

function updateRoleHint() {
  if (!roleSwitchHint || !roleSwitchHintText) return;
  if (roleHintDismissed) {
    roleSwitchHint.classList.add("hidden");
    return;
  }
  const pk = getConnectedPubkeySync();
  if (activeTab === "contributor") {
    if (pk) {
      roleSwitchHint.classList.add("hidden");
      return;
    }
    roleSwitchHintText.textContent = "Connect your Phantom wallet (devnet) to upload and submit recordings.";
    roleSwitchHint.classList.remove("hidden");
    return;
  }
  /* biologist */
  if (!biologistLoggedIn) {
    roleSwitchHintText.textContent = "Sign in as a biologist to open the review queue (demo login below).";
    roleSwitchHint.classList.remove("hidden");
    return;
  }
  if (!pk) {
    roleSwitchHintText.textContent =
      "Connect Phantom with your biologist (payer) wallet — you’ll sign the SOL transfer when you accept a live submission.";
    roleSwitchHint.classList.remove("hidden");
    return;
  }
  roleSwitchHint.classList.add("hidden");
}

function showRoleHintAfterTabSwitch() {
  roleHintDismissed = false;
  updateRoleHint();
}

async function sessionWalletAction() {
  const pk = getConnectedPubkeySync();
  if (pk) {
    stopBalancePolling();
    try {
      const p = getProvider();
      if (p?.disconnect) await p.disconnect();
    } catch {
      /* ignore */
    }
    showWalletUi(false);
    showBioWalletUi(false);
    clearWalletStats("contrib");
    clearWalletStats("bio");
    updateSessionBar();
    updateRoleHint();
    return;
  }
  if (activeTab === "contributor") {
    btnConnect.click();
    return;
  }
  if (!biologistLoggedIn) {
    alert("Sign in as a biologist first (below), then you can connect your wallet.");
    return;
  }
  btnBioConnect.click();
}

async function loadConfig() {
  try {
    config = await fetchJson("/api/contribute/config");
    if (config.rewardLamports == null && config.rewardSol != null) {
      config.rewardLamports = Math.round(Number(config.rewardSol) * 1e9);
    }
    if (config.rewardLamports == null) {
      config.rewardLamports = DEFAULT_REWARD_LAMPORTS;
    }
    if (config.rewardSol == null || !Number.isFinite(Number(config.rewardSol))) {
      config.rewardSol = config.rewardLamports / 1e9;
    }
    if (!config.rpcUrl) {
      config.rpcUrl = "https://api.devnet.solana.com";
    }
    const sol = config.rewardSol != null ? Number(config.rewardSol).toFixed(2) : "?";
    const mode = "Reviewer approves payout in Phantom — transfer goes to the contributor wallet on devnet.";
    if (rewardSolEl) rewardSolEl.textContent = `${sol} SOL`;
    if (rewardMetaEl) rewardMetaEl.textContent = `${config.network || "devnet"} · ${mode}`;
  } catch {
    if (rewardSolEl) rewardSolEl.textContent = "— SOL";
    if (rewardMetaEl) rewardMetaEl.textContent = "Could not load reward info.";
  }
}

/** Map CSV gender labels to stored `sex` values. */
function genderLabelToSex(label) {
  const t = String(label || "").trim();
  if (t === "Female") return "female";
  if (t === "Male") return "male";
  if (t === "N/A") return "unknown";
  return "unknown";
}

function fillSelect(el, options, placeholder) {
  if (!el) return;
  const opts = Array.isArray(options) ? options : [];
  el.innerHTML = "";
  const ph = document.createElement("option");
  ph.value = "";
  ph.textContent = placeholder || "—";
  el.appendChild(ph);
  for (const o of opts) {
    const opt = document.createElement("option");
    opt.value = o;
    opt.textContent = o;
    el.appendChild(opt);
  }
}

function refreshEthogramNamesForContext(ctx, preserveName) {
  if (!metaEthogramName || !ethogramOptions) return;
  const map = ethogramOptions.contextToNames || {};
  const names = map[ctx] || (ctx ? [] : ethogramOptions.allNames || []);
  fillSelect(metaEthogramName, names, names.length ? "—" : "No names for this context");
  if (preserveName && names.includes(preserveName)) {
    metaEthogramName.value = preserveName;
  }
}

async function loadEthogramOptions() {
  if (!metaEthogramContext) return;
  try {
    ethogramOptions = await fetchJson("/api/contribute/ethogram-options");
  } catch (e) {
    ethogramOptions = null;
    metaEthogramContext.innerHTML = "";
    const err = document.createElement("option");
    err.value = "";
    err.textContent = e.body?.error || e.message || "Could not load ethogram list";
    metaEthogramContext.appendChild(err);
    return;
  }
  fillSelect(metaEthogramContext, ethogramOptions.contexts || [], "—");
  refreshEthogramNamesForContext("", null);

  const genders = ethogramOptions.genders || [];
  if (metaGender) {
    metaGender.innerHTML = "";
    const ph = document.createElement("option");
    ph.value = "";
    ph.textContent = "—";
    metaGender.appendChild(ph);
    for (const g of genders) {
      const opt = document.createElement("option");
      opt.value = genderLabelToSex(g);
      opt.textContent = g;
      metaGender.appendChild(opt);
    }
  }
  fillSelect(metaAge, ethogramOptions.ages || [], "—");
  fillSelect(metaMode, ethogramOptions.modes || [], "—");
}

function syncDurationOtherVisibility() {
  if (!metaDuration || !metaDurationOther) return;
  const isOther = metaDuration.value === "__other__";
  metaDurationOther.classList.toggle("hidden", !isOther);
  metaDurationOther.required = isOther;
}

btnConnect.addEventListener("click", async () => {
  const p = getProvider();
  if (!p) {
    phantomHint.classList.remove("hidden");
    return;
  }
  setContribMsg("", "neutral");
  try {
    const r = await p.connect();
    const pk = r?.publicKey?.toBase58?.() || p.publicKey?.toBase58?.();
    showWalletUi(true, pk);
    await refreshWalletStatsForPubkey(pk);
    startBalancePolling(pk);
  } catch (e) {
    setContribMsg(e?.message || "Connect cancelled.", "err");
  }
  updateSessionBar();
  updateRoleHint();
});

btnDisconnect.addEventListener("click", async () => {
  const p = getProvider();
  setContribMsg("", "neutral");
  stopBalancePolling();
  try {
    if (p?.disconnect) await p.disconnect();
  } catch {
    /* ignore */
  }
  showWalletUi(false);
  clearWalletStats("contrib");
  updateSessionBar();
  updateRoleHint();
});

btnBioConnect.addEventListener("click", async () => {
  const p = getProvider();
  if (!p) {
    if (bioPhantomHint) bioPhantomHint.classList.remove("hidden");
    return;
  }
  if (bioPhantomHint) bioPhantomHint.classList.add("hidden");
  try {
    const r = await p.connect();
    const pk = r?.publicKey?.toBase58?.() || p.publicKey?.toBase58?.();
    showBioWalletUi(true, pk);
    await refreshWalletStatsForPubkey(pk);
    startBalancePolling(pk);
  } catch {
    /* cancelled */
  }
  updateSessionBar();
  updateRoleHint();
});

btnBioDisconnect.addEventListener("click", async () => {
  const p = getProvider();
  stopBalancePolling();
  try {
    if (p?.disconnect) await p.disconnect();
  } catch {
    /* ignore */
  }
  showBioWalletUi(false);
  clearWalletStats("bio");
  updateSessionBar();
  updateRoleHint();
});

if (sessionWalletBtn) sessionWalletBtn.addEventListener("click", () => sessionWalletAction());
if (sessionBioBtn) {
  sessionBioBtn.addEventListener("click", async () => {
    bioLogoutBtn.click();
  });
}

if (roleSwitchHintDismiss) {
  roleSwitchHintDismiss.addEventListener("click", () => {
    roleHintDismissed = true;
    if (roleSwitchHint) roleSwitchHint.classList.add("hidden");
  });
}

if (metaEthogramContext) {
  metaEthogramContext.addEventListener("change", () => {
    refreshEthogramNamesForContext(metaEthogramContext.value, null);
  });
}
if (metaDuration) {
  metaDuration.addEventListener("change", syncDurationOtherVisibility);
}

btnSubmit.addEventListener("click", async () => {
  setContribMsg("", "neutral");
  const pubkeyStr = await ensureWalletPubkey();
  if (!pubkeyStr) {
    setContribMsg("Connect your wallet first (click Connect wallet).", "err");
    return;
  }
  showWalletUi(true, pubkeyStr);
  const file = contribFile.files?.[0];
  if (!file) {
    setContribMsg("Choose a WAV file.", "err");
    return;
  }
  if (!ethogramOptions) {
    setContribMsg("Ethogram options did not load. Refresh the page.", "err");
    return;
  }
  const ethCtx = metaEthogramContext?.value?.trim() || "";
  const ethName = metaEthogramName?.value?.trim() || "";
  const situation = metaSituation?.value?.trim() || "";
  let duration = metaDuration?.value?.trim() || "";
  if (duration === "__other__") {
    duration = (metaDurationOther?.value?.trim() || "").slice(0, 200);
    if (!duration) {
      setContribMsg("Enter a duration, or pick a preset from the list.", "err");
      return;
    }
  }
  if (!ethCtx || !ethName) {
    setContribMsg("Choose ethogram context and call / behavior name.", "err");
    return;
  }
  if (!metaGender?.value || !metaAge?.value || !metaMode?.value) {
    setContribMsg("Select gender, age, and recording mode.", "err");
    return;
  }
  if (!duration) {
    setContribMsg("Choose clip duration.", "err");
    return;
  }
  const fd = new FormData();
  fd.append("wallet", pubkeyStr);
  fd.append("note", contribNote?.value?.trim() || "");
  fd.append("sex", metaGender?.value || "");
  fd.append("age", metaAge?.value?.trim() || "");
  fd.append("situation", situation);
  fd.append("duration", duration);
  fd.append("soundSegments", metaSounds?.value?.trim() || "");
  fd.append("ethogramContext", ethCtx);
  fd.append("ethogramName", ethName);
  fd.append("recordingMode", metaMode?.value?.trim() || "");
  fd.append("audio", file, file.name);
  btnSubmit.disabled = true;
  try {
    const data = await fetchJson("/api/contribute/submit", { method: "POST", body: fd });
    const sid = data.submission?.id ?? "?";
    setContribMsg(`Submitted successfully · id ${sid} · pending review.`, "ok");
    contribFile.value = "";
    if (contribNote) contribNote.value = "";
    if (metaEthogramContext) metaEthogramContext.value = "";
    refreshEthogramNamesForContext("", null);
    if (metaGender) metaGender.value = "";
    if (metaAge) metaAge.value = "";
    if (metaMode) metaMode.value = "";
    if (metaSituation) metaSituation.value = "";
    if (metaDuration) metaDuration.value = "";
    if (metaDurationOther) {
      metaDurationOther.value = "";
      metaDurationOther.classList.add("hidden");
    }
    if (metaSounds) metaSounds.value = "";
    await refreshWalletStatsForPubkey(pubkeyStr);
  } catch (e) {
    setContribMsg(e.body?.error || e.message || "Submit failed.", "err");
  } finally {
    btnSubmit.disabled = false;
  }
});

tabContributor.addEventListener("click", async () => {
  if (activeTab === "contributor") return;
  activeTab = "contributor";
  await resetAllSessions();
  setTab("contributor");
  await promptPhantomConnectForRole();
  showRoleHintAfterTabSwitch();
});

tabBiologist.addEventListener("click", async () => {
  if (activeTab === "biologist") return;
  activeTab = "biologist";
  await resetAllSessions();
  setTab("biologist");
  await checkBioSession();
  await promptPhantomConnectForRole();
  showRoleHintAfterTabSwitch();
});

async function checkBioSession() {
  try {
    const me = await fetchJson("/api/contribute/biologist/me");
    biologistLoggedIn = !!me?.loggedIn;
    if (bioLoginWrap) bioLoginWrap.classList.toggle("hidden", biologistLoggedIn);
    if (bioAfterLogin) bioAfterLogin.classList.toggle("hidden", !biologistLoggedIn);
    if (bioUserLabel) {
      bioUserLabel.textContent =
        biologistLoggedIn && me.username ? `Signed in as ${me.username}` : "";
    }
    if (biologistLoggedIn) await loadBioSubmissions();
    else if (bioList) bioList.innerHTML = "";
  } catch {
    biologistLoggedIn = false;
    if (bioUserLabel) bioUserLabel.textContent = "";
    if (bioLoginWrap) bioLoginWrap.classList.remove("hidden");
    if (bioAfterLogin) bioAfterLogin.classList.add("hidden");
  }
  updateSessionBar();
  updateRoleHint();
}

bioLoginBtn.addEventListener("click", async () => {
  bioLoginMsg.classList.add("hidden");
  try {
    await fetchJson("/api/contribute/biologist/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: bioUsername?.value ?? "",
        password: bioPassword?.value ?? "",
      }),
    });
    if (bioPassword) bioPassword.value = "";
    await checkBioSession();
    await syncBioWalletAfterLogin();
    updateRoleHint();
  } catch (e) {
    bioLoginMsg.textContent = e.body?.error || e.message || "Sign-in failed.";
    bioLoginMsg.classList.remove("hidden");
  }
});

bioLogoutBtn.addEventListener("click", async () => {
  try {
    await fetchJson("/api/contribute/biologist/logout", { method: "POST" });
  } catch {
    /* ignore */
  }
  biologistLoggedIn = false;
  mockReviewState = {};
  if (bioUserLabel) bioUserLabel.textContent = "";
  if (bioLoginWrap) bioLoginWrap.classList.remove("hidden");
  if (bioAfterLogin) bioAfterLogin.classList.add("hidden");
  if (bioList) bioList.innerHTML = "";
  updateSessionBar();
  updateRoleHint();
});

function mergeSubmissions(realList) {
  const realIds = new Set(realList.map((r) => r.id));
  const lam = config.rewardLamports ?? DEFAULT_REWARD_LAMPORTS;
  const mocks = MOCK_SUBMISSIONS.filter((m) => !realIds.has(m.id)).map((m) => {
    const st = mockReviewState[m.id] || m.status;
    return {
      ...m,
      status: st,
      txSignature: null,
      note: m.note,
      wallet: m.wallet,
      rewardLamports: lam,
      soundSegments: m.soundSegments,
    };
  });
  const merged = [...realList.map((r) => ({ ...r, isMock: false })), ...mocks];
  merged.sort((a, b) => {
    const pa = a.status === "pending" ? 0 : 1;
    const pb = b.status === "pending" ? 0 : 1;
    if (pa !== pb) return pa - pb;
    if (!a.isMock && b.isMock) return -1;
    if (a.isMock && !b.isMock) return 1;
    return String(b.id).localeCompare(String(a.id));
  });
  return merged;
}

function cardHtml(s) {
  const st = s.status || "pending";
  const isMock = !!s.isMock || String(s.id).startsWith("mock-");
  const ethoLine = [s.ethogramContext, s.ethogramName].filter(Boolean).join(" · ");
  const fallback = (s.situation || s.note || "") + "";
  const preview = ethoLine || fallback;
  const sit = (preview + "").slice(0, 120);
  const sitMore = (preview.length || 0) > 120 ? "…" : "";
  const badge = isMock
    ? `<span class="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded border border-[color:var(--accent-dim)] text-[color:var(--text-2)]">Sample</span>`
    : `<span class="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded border border-[color:var(--border)] text-[color:var(--text-2)]">Live</span>`;
  const txSig = s.txSignature || "";
  const txLine =
    st !== "pending" && txSig && !txSig.startsWith("MOCK:")
      ? `<a href="${explorerTxUrl(txSig, config.network)}" target="_blank" rel="noopener" class="text-[color:var(--accent)] underline text-[10px]">Tx</a>`
      : "";

  return `
    <div class="bio-card rounded-xl border border-[color:var(--border)] bg-[color:var(--bg-1)] p-4 w-full min-w-0 cursor-pointer transition-colors hover:border-[color:var(--accent-dim)] hover:bg-[color:var(--bg-2)]/40 text-left" data-card-id="${escapeHtml(String(s.id))}" role="button" tabindex="0">
      <div class="flex justify-between gap-2 flex-wrap items-start">
        <span class="mono text-xs text-[color:var(--accent)]">#${escapeHtml(String(s.id))}</span>
        <div class="flex items-center gap-2">
          ${badge}
          <span class="text-[10px] uppercase tracking-wider text-[color:var(--text-3)]">${st}</span>
          ${txLine}
        </div>
      </div>
      <p class="text-[10px] mono text-[color:var(--text-2)] mt-2">${walletShort(s.wallet)}</p>
      ${sit ? `<p class="text-xs text-[color:var(--text-1)] mt-2 leading-snug">${escapeHtml(sit)}${sitMore}</p>` : ""}
      <p class="text-[10px] text-[color:var(--accent)] mt-3 font-medium">Open for full metadata &amp; audio →</p>
    </div>`;
}

function escapeHtml(t) {
  const d = document.createElement("div");
  d.textContent = t;
  return d.innerHTML;
}

function walletShort(w) {
  const s = (w || "").trim();
  if (!s) return "—";
  return s.length > 14 ? `${s.slice(0, 8)}…${s.slice(-6)}` : s;
}

function formatSexLabel(v) {
  if (!v) return "—";
  const m = {
    unknown: "N/A",
    male: "Male",
    female: "Female",
    mixed: "Mixed / multiple",
  };
  const low = String(v).toLowerCase();
  if (m[low]) return m[low];
  if (v === "Female" || v === "Male" || v === "N/A") return v;
  return v;
}

function closeSubmissionModal() {
  if (!submissionModal) return;
  submissionModal.classList.add("hidden");
  submissionModal.setAttribute("aria-hidden", "true");
  if (modalAudio) {
    modalAudio.pause();
    modalAudio.removeAttribute("src");
    modalAudio.load();
  }
}

let modalOpenId = null;

function openSubmissionModal(id) {
  const s = submissionDetailCache[id];
  if (!s || !submissionModal) return;
  modalOpenId = id;
  submissionModal.classList.remove("hidden");
  submissionModal.setAttribute("aria-hidden", "false");
  if (modalSubId) modalSubId.textContent = `#${s.id}`;
  const isMock = !!s.isMock;
  if (modalSubBadge) modalSubBadge.textContent = isMock ? "Reference sample" : "Live submission";
  if (modalMetaEthogramContext) {
    modalMetaEthogramContext.textContent = (s.ethogramContext || "").trim() || "—";
  }
  if (modalMetaEthogramName) {
    modalMetaEthogramName.textContent = (s.ethogramName || "").trim() || "—";
  }
  if (modalMetaSex) modalMetaSex.textContent = formatSexLabel(s.sex);
  if (modalMetaAge) modalMetaAge.textContent = (s.age || "").trim() || "—";
  if (modalMetaMode) modalMetaMode.textContent = (s.recordingMode || "").trim() || "—";
  if (modalMetaDuration) modalMetaDuration.textContent = (s.duration || "").trim() || "—";
  const sitText = (s.situation || "").trim();
  if (modalMetaSituation) {
    modalMetaSituation.textContent = sitText || "—";
  }
  if (modalMetaSounds) modalMetaSounds.textContent = (s.soundSegments || "").trim() || "—";
  if (modalMetaWallet) modalMetaWallet.textContent = s.wallet || "—";
  const note = (s.note || "").trim();
  if (modalMetaNoteWrap && modalMetaNote) {
    if (note) {
      modalMetaNoteWrap.classList.remove("hidden");
      modalMetaNote.textContent = note;
    } else {
      modalMetaNoteWrap.classList.add("hidden");
    }
  }
  const st = s.status || "pending";
  const isMockRow = !!(s.isMock || String(s.id).startsWith("mock-"));
  const fileUrl = isMockRow ? "" : `${API}/api/contribute/file/${encodeURIComponent(s.id)}`;
  if (modalAudioWrap && modalAudio && modalNoAudio) {
    if (st === "pending" && fileUrl) {
      modalAudioWrap.classList.remove("hidden");
      modalNoAudio.classList.add("hidden");
      modalAudio.src = fileUrl;
    } else {
      modalAudioWrap.classList.add("hidden");
      modalNoAudio.classList.remove("hidden");
      modalAudio.removeAttribute("src");
    }
  }
  if (modalActions) {
    const canAct = st === "pending";
    modalActions.classList.toggle("hidden", !canAct);
  }
  if (modalBtnAccept && st === "pending") {
    const lam = s.rewardLamports ?? config.rewardLamports ?? DEFAULT_REWARD_LAMPORTS;
    const sol = (Number(lam) / 1e9).toFixed(2);
    modalBtnAccept.textContent = `Accept & pay ${sol} SOL`;
  }
}

async function loadBioSubmissions() {
  const data = await fetchJson("/api/contribute/biologist/submissions");
  const realList = data.submissions || [];
  const merged = mergeSubmissions(realList);
  submissionDetailCache = {};
  merged.forEach((row) => {
    submissionDetailCache[row.id] = row;
  });
  bioEmpty.classList.toggle("hidden", merged.length > 0);
  bioList.innerHTML = merged.map(cardHtml).join("");
}

if (bioList) {
  bioList.addEventListener("click", (e) => {
    const card = e.target.closest(".bio-card");
    if (!card?.dataset.cardId) return;
    openSubmissionModal(card.dataset.cardId);
  });
  bioList.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const card = e.target.closest(".bio-card");
    if (!card?.dataset.cardId) return;
    e.preventDefault();
    openSubmissionModal(card.dataset.cardId);
  });
}

if (submissionModalBackdrop) {
  submissionModalBackdrop.addEventListener("click", () => closeSubmissionModal());
}
if (submissionModalClose) {
  submissionModalClose.addEventListener("click", () => closeSubmissionModal());
}
function showAcceptCelebration({ isMock, solAmount, txSig }) {
  if (!acceptCelebrationRoot || !acceptCelebrationTitle || !acceptCelebrationSub) return;
  acceptCelebrationRoot.classList.remove("hidden");
  acceptCelebrationRoot.setAttribute("aria-hidden", "false");
  acceptCelebrationRoot.classList.remove("is-leaving");

  const solLabel =
    typeof solAmount === "number" && Number.isFinite(solAmount)
      ? solAmount.toFixed(2)
      : (config.rewardSol != null ? Number(config.rewardSol).toFixed(2) : "1.50");

  if (isMock) {
    acceptCelebrationTitle.textContent = "Accepted (sample)";
    acceptCelebrationSub.textContent =
      "This reference card was marked accepted. On a live submission, Phantom would prompt you to send " +
      solLabel +
      " SOL on devnet to the contributor wallet.";
    if (acceptCelebrationExplorer) {
      acceptCelebrationExplorer.classList.add("hidden");
      acceptCelebrationExplorer.href = "#";
    }
  } else {
    acceptCelebrationTitle.textContent = "Accepted · reward sent";
    acceptCelebrationSub.textContent =
      "You sent " + solLabel + " SOL to the contributor on Solana devnet. The submission is recorded as accepted.";
    if (acceptCelebrationExplorer && txSig) {
      acceptCelebrationExplorer.href = explorerTxUrl(txSig, config.network);
      acceptCelebrationExplorer.classList.remove("hidden");
    } else if (acceptCelebrationExplorer) {
      acceptCelebrationExplorer.classList.add("hidden");
    }
  }
}

function hideAcceptCelebration() {
  if (!acceptCelebrationRoot) return;
  const prev = acceptCelebrationRoot.dataset.hideTimer;
  if (prev) window.clearTimeout(Number(prev));
  acceptCelebrationRoot.classList.add("is-leaving");
  const t = window.setTimeout(() => {
    acceptCelebrationRoot.classList.add("hidden");
    acceptCelebrationRoot.classList.remove("is-leaving");
    acceptCelebrationRoot.setAttribute("aria-hidden", "true");
    delete acceptCelebrationRoot.dataset.hideTimer;
  }, 280);
  acceptCelebrationRoot.dataset.hideTimer = String(t);
}

if (acceptCelebrationDismiss) {
  acceptCelebrationDismiss.addEventListener("click", () => hideAcceptCelebration());
}
if (acceptCelebrationRoot) {
  acceptCelebrationRoot.addEventListener("click", (e) => {
    if (e.target === acceptCelebrationRoot) hideAcceptCelebration();
  });
}
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (acceptCelebrationRoot && !acceptCelebrationRoot.classList.contains("hidden")) {
    hideAcceptCelebration();
  }
});

if (modalBtnAccept) {
  modalBtnAccept.addEventListener("click", async () => {
    if (!modalOpenId) return;
    const s = submissionDetailCache[modalOpenId];
    const isMock = !!(s?.isMock || String(modalOpenId).startsWith("mock-"));
    const rewardLamports = s?.rewardLamports ?? config.rewardLamports ?? DEFAULT_REWARD_LAMPORTS;
    const ds = {
      to: s?.wallet,
      lamports: String(rewardLamports),
    };
    const origLabel = modalBtnAccept.textContent;
    modalBtnAccept.disabled = true;
    if (modalBtnReject) modalBtnReject.disabled = true;
    modalBtnAccept.textContent = isMock ? "Accepting…" : "Waiting for Phantom…";
    try {
      const out = await review(modalOpenId, "accept", isMock, ds);
      if (out?.ok && out?.accepted) {
        showAcceptCelebration({
          isMock: !!out.isMock,
          solAmount: out.solAmount,
          txSig: out.txSig,
        });
        closeSubmissionModal();
      }
    } finally {
      modalBtnAccept.disabled = false;
      if (modalBtnReject) modalBtnReject.disabled = false;
      modalBtnAccept.textContent = origLabel;
    }
  });
}
if (modalBtnReject) {
  modalBtnReject.addEventListener("click", async () => {
    if (!modalOpenId) return;
    const s = submissionDetailCache[modalOpenId];
    const isMock = !!(s?.isMock || String(modalOpenId).startsWith("mock-"));
    await review(modalOpenId, "reject", isMock, {});
    closeSubmissionModal();
  });
}

async function getConnectedPubkey() {
  const p = getProvider();
  if (!p?.publicKey) return null;
  return p.publicKey.toBase58?.() || null;
}

async function review(id, action, isMock, dataset) {
  if (isMock) {
    mockReviewState[id] = action === "accept" ? "accepted" : "rejected";
    await loadBioSubmissions();
    if (action === "accept") {
      const lam = Number(dataset?.lamports ?? config.rewardLamports ?? DEFAULT_REWARD_LAMPORTS);
      return {
        ok: true,
        accepted: true,
        isMock: true,
        solAmount: Number.isFinite(lam) ? lam / 1e9 : config.rewardSol ?? 1.5,
      };
    }
    return { ok: true, accepted: false };
  }
  if (action === "reject") {
    try {
      await fetchJson(`/api/contribute/biologist/review/${encodeURIComponent(id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reject" }),
      });
      await loadBioSubmissions();
      const pk = await getConnectedPubkey();
      if (pk) await refreshWalletStatsForPubkey(pk);
    } catch (e) {
      alert(e.body?.error || e.message || "Review failed.");
      return { ok: false, accepted: false };
    }
    return { ok: true, accepted: false };
  }

  const sub = submissionDetailCache[id];
  const toWallet = (dataset?.to || sub?.wallet || "").trim();
  const lamports = Number(dataset?.lamports ?? sub?.rewardLamports ?? config.rewardLamports ?? DEFAULT_REWARD_LAMPORTS);
  if (!toWallet || !Number.isFinite(lamports) || lamports <= 0) {
    alert("Missing payout details. Reload the page after config loads.");
    return { ok: false, accepted: false };
  }
  const provider = getProvider();
  if (!provider) {
    alert("Install Phantom to send the reward.");
    return { ok: false, accepted: false };
  }
  try {
    await provider.connect();
  } catch {
    return { ok: false, accepted: false };
  }
  const fromPk = provider.publicKey?.toBase58?.();
  if (!fromPk) {
    alert("Connect your biologist wallet in Phantom.");
    return { ok: false, accepted: false };
  }
  if (fromPk === toWallet) {
    alert(
      "Contributor wallet matches your biologist wallet. Switch Phantom accounts or use two wallets for demo."
    );
    return { ok: false, accepted: false };
  }
  let txSig;
  try {
    txSig = await sendRewardFromBiologistWallet({ fromPubkey: fromPk, toWallet, lamports });
  } catch (e) {
    const msg = e?.message || String(e) || "Transfer failed.";
    alert(msg);
    return { ok: false, accepted: false };
  }
  try {
    await fetchJson(`/api/contribute/biologist/review/${encodeURIComponent(id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "accept", txSignature: txSig }),
    });
    await loadBioSubmissions();
    const pk = await getConnectedPubkey();
    if (pk) await refreshWalletStatsForPubkey(pk);
    return {
      ok: true,
      accepted: true,
      isMock: false,
      txSig,
      solAmount: lamports / 1e9,
    };
  } catch (e) {
    alert(
      e.body?.error ||
        e.message ||
        "Transfer succeeded but server could not record acceptance. Check Explorer for the transaction."
    );
    return { ok: false, accepted: false };
  }
}

(async () => {
  await loadConfig();
  await loadEthogramOptions();
  syncDurationOtherVisibility();
  await promptPhantomConnectForRole();
  updateSessionBar();
  updateRoleHint();
})();
