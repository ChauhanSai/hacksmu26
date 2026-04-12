"""
Load hackathon rumble annotations from CSV (Sound_file, Start_time, End_time, Call_type).
Used to align cleaning windows with human labels across all clips in the dataset.
"""

from __future__ import annotations

import csv
from pathlib import Path

from elephant_audio_cleaner import DetectionSegment

# Default path relative to repo root (copy of hackathon master sheet)
DEFAULT_RUMBLE_CSV = Path(__file__).resolve().parent / "data" / "rumbles_in_noise_for_hackathon.csv"


def _rumble_row(call_type: str) -> bool:
    t = (call_type or "").strip().lower()
    return "rumble" in t


def load_rumble_csv(path: str | Path) -> dict[str, list[tuple[DetectionSegment, str]]]:
    """
    Map basename (e.g. 04-040920-02_vehicle_1.wav) -> list of (segment, call_type).
    Only rows whose Call_type contains 'rumble' are included (covers bark-rumble, etc.).
    """
    path = Path(path)
    out: dict[str, list[tuple[DetectionSegment, str]]] = {}
    if not path.is_file():
        return out

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sound = (row.get("Sound_file") or "").strip()
            if not sound:
                continue
            call_type = (row.get("Call_type") or "").strip()
            if not _rumble_row(call_type):
                continue
            try:
                start = float(row["Start_time"])
                end = float(row["End_time"])
            except (KeyError, ValueError, TypeError):
                continue
            if end <= start or start < 0:
                continue
            seg = DetectionSegment(start=float(start), end=float(end))
            out.setdefault(sound, []).append((seg, call_type))

    for key in out:
        out[key].sort(key=lambda x: (x[0].start, x[0].end))
    return out


def lookup_segments(
    index: dict[str, list[tuple[DetectionSegment, str]]],
    filename: str,
) -> list[tuple[DetectionSegment, str]] | None:
    """Match uploaded filename to CSV basename (case-insensitive)."""
    base = Path(filename).name
    if base in index:
        return index[base]
    lower = base.lower()
    for k, v in index.items():
        if k.lower() == lower:
            return v
    return None


def merge_for_processing(
    rows: list[tuple[DetectionSegment, str]],
    duration_sec: float,
    pad: float,
) -> list[DetectionSegment]:
    """
    Pad each window, clamp to [0, duration], then merge overlaps into a union
    for noise masking and time gating.
    """
    padded: list[DetectionSegment] = []
    for seg, _ in rows:
        s = max(0.0, seg.start - pad)
        e = min(duration_sec, seg.end + pad)
        if e - s > 0.05:
            padded.append(DetectionSegment(s, e))
    if not padded:
        return []
    padded.sort(key=lambda x: (x.start, x.end))
    merged: list[DetectionSegment] = [padded[0]]
    for seg in padded[1:]:
        last = merged[-1]
        if seg.start <= last.end + 1e-3:
            merged[-1] = DetectionSegment(last.start, max(last.end, seg.end))
        else:
            merged.append(seg)
    return merged


def pad_segments_for_display(
    rows: list[tuple[DetectionSegment, str]],
    duration_sec: float,
    pad: float,
) -> list[tuple[DetectionSegment, str]]:
    """Per-row padded segments for API / timeline (may overlap)."""
    out: list[tuple[DetectionSegment, str]] = []
    for seg, ctype in rows:
        s = max(0.0, seg.start - pad)
        e = min(duration_sec, seg.end + pad)
        if e - s > 0.05:
            out.append((DetectionSegment(s, e), ctype))
    return out
