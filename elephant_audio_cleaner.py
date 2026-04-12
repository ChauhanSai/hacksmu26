from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter1d, uniform_filter1d
from scipy.signal import butter, filtfilt, find_peaks, hilbert, istft, stft


# Detection is more stable with the time/frequency tradeoff reported in Keen et al.
NFFT = 1024
HOP = 200
WINDOW = "hann"
RUMBLE_LO = 8.0
F0_LO = 10.0
F0_HI = 34.0
CORE_BAND_HI = 64.0
HARMONIC_HI = 180.0
DISPLAY_HI = 700.0
OUTPUT_HI = 180.0
ALPHA = 1.8
BETA = 0.01
MIN_RUMBLE_DUR = 1.0
MAX_RUMBLE_DUR = 5.0
MIN_GAP_DUR = 0.20
SEGMENT_PAD = 0.35


@dataclass
class DetectionSegment:
    start: float
    end: float


@dataclass
class CleaningSummary:
    segments: list[DetectionSegment]
    elephant_band: tuple[int, int]
    tonal_lines_hz: list[float]
    peak_noise_hz: float
    duration_seconds: float


def load_audio(path: str | Path) -> tuple[np.ndarray, int]:
    waveform, sr = sf.read(path)
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    return waveform.astype(np.float64), sr


def compute_spectrogram(waveform: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    freqs, times, zxx = stft(
        waveform,
        fs=sr,
        nperseg=NFFT,
        noverlap=NFFT - HOP,
        window=WINDOW,
    )
    return freqs, times, zxx


def band_mask(freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return (freqs >= lo) & (freqs <= hi)


def smooth_frames(values: np.ndarray, sigma_frames: float = 3.0) -> np.ndarray:
    return gaussian_filter1d(values, sigma=sigma_frames, mode="nearest")


def robust_zscore(values: np.ndarray) -> np.ndarray:
    median = np.median(values)
    mad = np.median(np.abs(values - median)) + 1e-9
    return (values - median) / (1.4826 * mad)


def detect_rumble_regions(freqs: np.ndarray, times: np.ndarray, magnitude: np.ndarray) -> list[DetectionSegment]:
    power = magnitude ** 2
    display_mask = band_mask(freqs, RUMBLE_LO, DISPLAY_HI)
    f0_mask = band_mask(freqs, F0_LO, F0_HI)
    core_mask = band_mask(freqs, RUMBLE_LO, CORE_BAND_HI)
    harmonic_mask = band_mask(freqs, CORE_BAND_HI, HARMONIC_HI)
    noise_mask = band_mask(freqs, 180.0, DISPLAY_HI)

    total_low = np.log1p(power[display_mask, :].sum(axis=0))
    f0_energy = np.log1p(power[f0_mask, :].sum(axis=0))
    core_energy = np.log1p(power[core_mask, :].sum(axis=0))
    harmonic_energy = np.log1p(power[harmonic_mask, :].sum(axis=0))
    noise_energy = np.log1p(power[noise_mask, :].sum(axis=0))
    harmonic_ratio = (power[core_mask | harmonic_mask, :].sum(axis=0) + 1e-9) / (
        power[display_mask, :].sum(axis=0) + 1e-9
    )

    # Broad region score: where rumble-like low-frequency structure dominates.
    broad_score = (
        0.40 * robust_zscore(smooth_frames(f0_energy, 2.5))
        + 0.30 * robust_zscore(smooth_frames(core_energy, 2.5))
        + 0.20 * robust_zscore(smooth_frames(harmonic_energy, 3.0))
        + 0.15 * robust_zscore(smooth_frames(np.log1p(harmonic_ratio), 2.5))
        - 0.30 * robust_zscore(smooth_frames(noise_energy, 3.0))
        + 0.08 * robust_zscore(smooth_frames(total_low, 2.5))
    )
    broad_score = smooth_frames(broad_score, sigma_frames=4.0)

    threshold = np.percentile(broad_score, 50)
    support = broad_score > threshold
    support |= harmonic_ratio > max(0.20, np.percentile(harmonic_ratio, 45))

    frame_step = times[1] - times[0] if len(times) > 1 else HOP / 44100.0

    # Call-level envelope: low-band energy on a shorter timescale so overlapping
    # calls inside one broad region can become separate windows.
    nyquist = DISPLAY_HI  # placeholder to make mypy happy
    call_envelope = smooth_frames(
        0.65 * core_energy + 0.35 * harmonic_energy - 0.20 * noise_energy,
        sigma_frames=1.8,
    )
    call_envelope = call_envelope - np.median(call_envelope)
    call_baseline = np.percentile(call_envelope, 25)
    peak_distance = max(1, int(0.8 / frame_step))

    prominence = max(np.std(call_envelope) * 0.16, 0.06)
    peaks, _ = find_peaks(call_envelope, distance=peak_distance, prominence=prominence)
    segments: list[DetectionSegment] = []
    for peak_idx in peaks:
        left_support = max(0, peak_idx - int(0.6 / frame_step))
        right_support = min(len(times), peak_idx + int(0.6 / frame_step))
        if not np.any(support[left_support:right_support]):
            continue

        peak_val = call_envelope[peak_idx]
        floor = max(call_baseline, peak_val * 0.42)

        left = peak_idx
        while left > 0 and call_envelope[left] > floor:
            left -= 1
        right = peak_idx
        while right < len(call_envelope) - 1 and call_envelope[right] > floor:
            right += 1

        seg_start = max(times[0], times[left] - SEGMENT_PAD)
        seg_end = min(times[-1], times[right] + SEGMENT_PAD)
        duration = seg_end - seg_start

        if duration < MIN_RUMBLE_DUR:
            extra = (MIN_RUMBLE_DUR - duration) / 2.0
            seg_start = max(times[0], seg_start - extra)
            seg_end = min(times[-1], seg_end + extra)
            duration = seg_end - seg_start
        if duration > MAX_RUMBLE_DUR:
            center = times[peak_idx]
            half = MAX_RUMBLE_DUR / 2.0
            seg_start = max(times[0], center - half)
            seg_end = min(times[-1], center + half)

        if seg_end - seg_start >= MIN_RUMBLE_DUR * 0.95:
            segments.append(DetectionSegment(float(seg_start), float(seg_end)))

    if not segments:
        return []

    # Remove near-duplicate windows but keep genuine overlaps.
    segments.sort(key=lambda segment: (segment.start, segment.end))
    deduped: list[DetectionSegment] = []
    for segment in segments:
        duplicate = False
        for existing in deduped:
            overlap = max(0.0, min(segment.end, existing.end) - max(segment.start, existing.start))
            union = max(segment.end, existing.end) - min(segment.start, existing.start)
            if union > 0 and overlap / union > 0.82:
                duplicate = True
                break
        if not duplicate:
            deduped.append(segment)

    # Long low-frequency episodes can contain multiple overlapping annotations.
    # If the peak-based pass still collapses them, derive nested windows from the
    # strongest broad region at multiple relative thresholds.
    if len(deduped) < 2:
        peak_idx = int(np.argmax(call_envelope))
        peak_val = call_envelope[peak_idx]
        broad_floor = max(call_baseline, np.percentile(call_envelope, 40))
        region_left = peak_idx
        while region_left > 0 and call_envelope[region_left] > broad_floor:
            region_left -= 1
        region_right = peak_idx
        while region_right < len(call_envelope) - 1 and call_envelope[region_right] > broad_floor:
            region_right += 1

        nested: list[DetectionSegment] = []
        peak_time = float(times[peak_idx])
        left_extent = max(0.0, peak_time - float(times[region_left]))
        right_extent = max(0.0, float(times[region_right]) - peak_time)

        if left_extent + right_extent >= 5.0:
            start_scales = (0.95, 0.60, 0.25)
            end_scales = (0.18, 0.48, 0.98)
            for start_scale, end_scale in zip(start_scales, end_scales):
                seg_start = max(float(times[region_left]), peak_time - start_scale * left_extent)
                seg_end = min(float(times[region_right]), peak_time + end_scale * right_extent)
                if seg_end - seg_start >= MIN_RUMBLE_DUR * 0.95:
                    nested.append(DetectionSegment(seg_start, seg_end))

        nested.sort(key=lambda segment: (segment.start, segment.end))
        if len(nested) >= 2:
            deduped = nested

    return deduped


def estimate_noise_power(magnitude: np.ndarray, keep_mask: np.ndarray) -> np.ndarray:
    if np.any(~keep_mask):
        reference = magnitude[:, ~keep_mask]
    else:
        frame_energy = magnitude.sum(axis=0)
        n_quiet = max(5, int(0.2 * magnitude.shape[1]))
        quiet_idx = np.argsort(frame_energy)[:n_quiet]
        reference = magnitude[:, quiet_idx]
    return np.mean(reference ** 2, axis=1, keepdims=True)


def detect_tonal_lines(noise_power: np.ndarray, freqs: np.ndarray) -> list[float]:
    pwr_db = 10 * np.log10(noise_power[:, 0] + 1e-12)
    smoothed = uniform_filter1d(pwr_db, size=31, mode="nearest")
    excess = pwr_db - smoothed
    tonal_idx = np.where((excess > 5.0) & (freqs >= 20.0) & (freqs <= OUTPUT_HI))[0]
    if len(tonal_idx) == 0:
        return []

    grouped: list[list[int]] = [[int(tonal_idx[0])]]
    for idx in tonal_idx[1:]:
        if idx - grouped[-1][-1] <= 3:
            grouped[-1].append(int(idx))
        else:
            grouped.append([int(idx)])

    return [float(freqs[int(np.mean(group))]) for group in grouped]


def soft_frequency_mask(freqs: np.ndarray) -> np.ndarray:
    mask = np.zeros_like(freqs, dtype=np.float64)
    for index, freq in enumerate(freqs):
        if freq < RUMBLE_LO:
            if freq > 1.0:
                mask[index] = (freq - 1.0) / (RUMBLE_LO - 1.0)
        elif freq <= HARMONIC_HI:
            mask[index] = 1.0
        elif freq <= OUTPUT_HI:
            mask[index] = max(0.0, 1.0 - (freq - HARMONIC_HI) / (OUTPUT_HI - HARMONIC_HI))
        else:
            mask[index] = 0.0
    return mask[:, np.newaxis]


def build_time_mask(times: np.ndarray, segments: list[DetectionSegment]) -> np.ndarray:
    if not segments:
        return np.ones((1, len(times)), dtype=np.float64)

    mask = np.zeros(len(times), dtype=np.float64)
    for segment in segments:
        seg_start = segment.start
        seg_end = segment.end
        active = (times >= seg_start) & (times <= seg_end)
        mask[active] = 1.0

    mask = gaussian_filter1d(mask, sigma=2.0, mode="nearest")
    return np.clip(mask, 0.0, 1.0)[np.newaxis, :]


def clean_audio(audio_path: str | Path, output_path: str | Path) -> CleaningSummary:
    waveform, sr = load_audio(audio_path)
    freqs, times, zxx = compute_spectrogram(waveform, sr)
    magnitude = np.abs(zxx)

    segments = detect_rumble_regions(freqs, times, magnitude)
    keep_mask = np.zeros(len(times), dtype=bool)
    for segment in segments:
        keep_mask |= (times >= segment.start) & (times <= segment.end)

    noise_power = estimate_noise_power(magnitude, keep_mask)
    tonal_lines = detect_tonal_lines(noise_power, freqs)

    power = magnitude ** 2
    cleaned_power = np.maximum(power - ALPHA * noise_power, BETA * power)
    cleaned_mag = np.sqrt(cleaned_power)

    signal_power = np.maximum(cleaned_mag ** 2, noise_power)
    snr = signal_power / (noise_power + 1e-12)
    gain = snr / (snr + 1.0)
    cleaned_mag *= gain

    for tonal_hz in tonal_lines:
        bin_idx = int(np.argmin(np.abs(freqs - tonal_hz)))
        lo = max(0, bin_idx - 2)
        hi = min(cleaned_mag.shape[0], bin_idx + 3)
        cleaned_mag[lo:hi, :] *= 0.18

    cleaned_mag *= soft_frequency_mask(freqs)
    cleaned_mag *= build_time_mask(times, segments)

    ratio = np.where(magnitude > 1e-10, cleaned_mag / (magnitude + 1e-10), 0.0)
    zxx_clean = zxx * ratio
    _, cleaned_wave = istft(
        zxx_clean,
        fs=sr,
        nperseg=NFFT,
        noverlap=NFFT - HOP,
        window=WINDOW,
    )

    if sr / 2 > OUTPUT_HI + 5:
        nyquist = sr / 2.0
        b, a = butter(4, RUMBLE_LO / nyquist, btype="high")
        cleaned_wave = filtfilt(b, a, cleaned_wave)
        b, a = butter(4, min(OUTPUT_HI, nyquist * 0.95) / nyquist, btype="low")
        cleaned_wave = filtfilt(b, a, cleaned_wave)

    peak = np.max(np.abs(cleaned_wave))
    if peak > 1e-10:
        cleaned_wave = 0.7 * cleaned_wave / peak

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, cleaned_wave, sr)

    valid_peak_bins = np.where(freqs >= RUMBLE_LO)[0]
    if len(valid_peak_bins) > 0:
        peak_bin = valid_peak_bins[int(np.argmax(noise_power[valid_peak_bins, 0]))]
        peak_noise_hz = float(freqs[peak_bin])
    else:
        peak_noise_hz = 0.0
    return CleaningSummary(
        segments=segments,
        elephant_band=(int(RUMBLE_LO), int(OUTPUT_HI)),
        tonal_lines_hz=tonal_lines,
        peak_noise_hz=peak_noise_hz,
        duration_seconds=len(waveform) / sr,
    )


def plot_spectrogram(audio_path: str | Path, image_path: str | Path, title: str) -> None:
    waveform, sr = load_audio(audio_path)
    freqs, times, zxx = compute_spectrogram(waveform, sr)

    valid = freqs <= DISPLAY_HI
    power_db = 20 * np.log10(np.abs(zxx[valid, :]) + 1e-8)

    fig, ax = plt.subplots(figsize=(10.5, 4.8), dpi=180)
    mesh = ax.pcolormesh(times, freqs[valid], power_db, shading="gouraud", cmap="magma")
    ax.set_title(title, fontsize=12, pad=12)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_ylim(0, DISPLAY_HI)
    ax.set_facecolor("#110d16")
    fig.patch.set_facecolor("#fffdf8")
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("Amplitude (dB)")
    fig.tight_layout()
    Path(image_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(image_path, bbox_inches="tight")
    plt.close(fig)
