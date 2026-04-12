from __future__ import annotations

import os
import uuid
from pathlib import Path

import soundfile as sf
from flask import Flask, abort, jsonify, request, send_file, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename

from contribute_api import register_contribute_routes
from elephant_audio_cleaner import SEGMENT_PAD, clean_audio, plot_spectrogram
from rumble_annotations import load_rumble_csv, lookup_segments, merge_for_processing, pad_segments_for_display


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "cleaned_output_web"
SPECTROGRAM_DIR = BASE_DIR / "generated_spectrograms"
ALLOWED_AUDIO_EXTENSIONS = {".wav"}

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
SPECTROGRAM_DIR.mkdir(exist_ok=True)

_ANNOTATION_INDEX: dict | None = None


def get_annotation_index() -> dict:
    """Load hackathon rumble CSV once (path override via RUMBLE_CSV env)."""
    global _ANNOTATION_INDEX
    if _ANNOTATION_INDEX is None:
        csv_path = Path(os.environ.get("RUMBLE_CSV", str(BASE_DIR / "data" / "rumbles_in_noise_for_hackathon.csv")))
        _ANNOTATION_INDEX = load_rumble_csv(csv_path) if csv_path.is_file() else {}
    return _ANNOTATION_INDEX


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-tusk-tidy-secret-change-me")
CORS(app, supports_credentials=True)

register_contribute_routes(app, BASE_DIR)


def allowed_audio(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_AUDIO_EXTENSIONS


@app.route("/api/clean", methods=["POST"])
def api_clean():
    """JSON API endpoint for the frontend cleanup page."""
    uploaded_audio = request.files.get("audio")

    if uploaded_audio is None or uploaded_audio.filename == "":
        return jsonify({"error": "Choose a WAV file to process."}), 400

    if not allowed_audio(uploaded_audio.filename):
        return jsonify({"error": "Only WAV audio uploads are supported."}), 400

    token = uuid.uuid4().hex
    safe_audio_name = secure_filename(uploaded_audio.filename)

    input_audio_path = UPLOAD_DIR / f"{token}_{safe_audio_name}"
    output_audio_name = f"{Path(safe_audio_name).stem}_elephant_only.wav"
    output_audio_path = OUTPUT_DIR / f"{token}_{output_audio_name}"
    before_spectrogram_path = SPECTROGRAM_DIR / f"{token}_{Path(safe_audio_name).stem}_before.png"
    after_spectrogram_path = SPECTROGRAM_DIR / f"{token}_{Path(safe_audio_name).stem}_after.png"

    uploaded_audio.save(input_audio_path)

    try:
        plot_spectrogram(input_audio_path, before_spectrogram_path, "Before Cleaning")
        duration_sec = float(sf.info(str(input_audio_path)).duration)
        rows = lookup_segments(get_annotation_index(), safe_audio_name)
        if rows:
            merged = merge_for_processing(rows, duration_sec, SEGMENT_PAD)
            display = pad_segments_for_display(rows, duration_sec, SEGMENT_PAD)
            if merged:
                summary = clean_audio(
                    input_audio_path,
                    output_audio_path,
                    segments_merged=merged,
                    segments_display=display,
                )
            else:
                summary = clean_audio(input_audio_path, output_audio_path)
        else:
            summary = clean_audio(input_audio_path, output_audio_path)
        plot_spectrogram(output_audio_path, after_spectrogram_path, "After Cleaning")
    except Exception as exc:
        return jsonify({"error": f"Cleaning failed: {exc}"}), 500

    tonal_text = (
        ", ".join(f"{hz:.0f} Hz" for hz in summary.tonal_lines_hz[:4])
        if summary.tonal_lines_hz
        else "no strong stationary tonal lines detected"
    )
    if summary.annotations_source == "csv":
        summary_line = (
            f"Hackathon CSV: {len(summary.segments)} labeled rumble window(s). "
            f"Kept {summary.elephant_band[0]}–{summary.elephant_band[1]} Hz; "
            f"noise profile peak ~{summary.peak_noise_hz:.1f} Hz. "
            f"Tonal suppression: {tonal_text}."
        )
    else:
        summary_line = (
            f"Detected {len(summary.segments) or 1} likely rumble region(s), "
            f"kept roughly {summary.elephant_band[0]}–{summary.elephant_band[1]} Hz, "
            f"and used a noise profile peaking near {summary.peak_noise_hz:.1f} Hz. "
            f"Tonal suppression target: {tonal_text}."
        )

    return jsonify({
        "audio_url": url_for("download_audio", filename=output_audio_path.name, _external=True),
        "audio_download_name": output_audio_name,
        "before_image_url": url_for("spectrogram_asset", filename=before_spectrogram_path.name, _external=True),
        "after_image_url": url_for("spectrogram_asset", filename=after_spectrogram_path.name, _external=True),
        "original_name": safe_audio_name,
        "annotations_source": summary.annotations_source,
        "segments": [
            {
                "label": (
                    summary.segment_labels[i]
                    if summary.segment_labels and i < len(summary.segment_labels)
                    else f"Rumble {i + 1}"
                ),
                "start": f"{segment.start:.2f}",
                "end": f"{segment.end:.2f}",
            }
            for i, segment in enumerate(summary.segments)
        ],
        "duration_seconds": f"{summary.duration_seconds:.2f}",
        "summary_line": summary_line,
    })


@app.route("/", methods=["GET"])
def index():
    """Serve the static landing page (no Jinja template; live under frontend/)."""
    return send_file(BASE_DIR / "frontend" / "index.html")


@app.route("/downloads/<path:filename>")
def download_audio(filename: str):
    return send_file(OUTPUT_DIR / filename, as_attachment=False)


@app.route("/spectrograms/<path:filename>")
def spectrogram_asset(filename: str):
    return send_file(SPECTROGRAM_DIR / filename, as_attachment=False)


@app.route("/<path:subpath>")
def serve_frontend(subpath: str):
    """Serve static assets and other HTML pages from frontend/ when using Flask as the only server."""
    candidate = (BASE_DIR / "frontend" / subpath).resolve()
    base = (BASE_DIR / "frontend").resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        abort(404)
    if not candidate.is_file():
        abort(404)
    return send_file(candidate)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
