from __future__ import annotations

import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename

from elephant_audio_cleaner import clean_audio, plot_spectrogram


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "cleaned_output_web"
SPECTROGRAM_DIR = BASE_DIR / "generated_spectrograms"
ALLOWED_AUDIO_EXTENSIONS = {".wav"}

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
SPECTROGRAM_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
CORS(app)


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
        summary = clean_audio(input_audio_path, output_audio_path)
        plot_spectrogram(output_audio_path, after_spectrogram_path, "After Cleaning")
    except Exception as exc:
        return jsonify({"error": f"Cleaning failed: {exc}"}), 500

    tonal_text = (
        ", ".join(f"{hz:.0f} Hz" for hz in summary.tonal_lines_hz[:4])
        if summary.tonal_lines_hz
        else "no strong stationary tonal lines detected"
    )
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
        "segments": [
            {
                "label": f"Rumble {index + 1}",
                "start": f"{segment.start:.2f}",
                "end": f"{segment.end:.2f}",
            }
            for index, segment in enumerate(summary.segments)
        ],
        "duration_seconds": f"{summary.duration_seconds:.2f}",
        "summary_line": summary_line,
    })


@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "error": None,
        "audio_url": None,
        "audio_download_name": None,
        "before_image_url": None,
        "after_image_url": None,
        "original_name": None,
        "segments": [],
        "summary_line": None,
        "duration_seconds": None,
    }

    if request.method == "POST":
        uploaded_audio = request.files.get("audio")

        if uploaded_audio is None or uploaded_audio.filename == "":
            context["error"] = "Choose a WAV file to process."
            return render_template("index.html", **context)

        if not allowed_audio(uploaded_audio.filename):
            context["error"] = "Only WAV audio uploads are supported right now."
            return render_template("index.html", **context)

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
            summary = clean_audio(input_audio_path, output_audio_path)
            plot_spectrogram(output_audio_path, after_spectrogram_path, "After Cleaning")
        except Exception as exc:
            context["error"] = f"Cleaning failed: {exc}"
            return render_template("index.html", **context)

        context["audio_url"] = url_for("download_audio", filename=output_audio_path.name)
        context["audio_download_name"] = output_audio_name
        context["before_image_url"] = url_for("spectrogram_asset", filename=before_spectrogram_path.name)
        context["after_image_url"] = url_for("spectrogram_asset", filename=after_spectrogram_path.name)
        context["original_name"] = safe_audio_name
        context["segments"] = [
            {
                "label": f"Rumble {index + 1}",
                "start": f"{segment.start:.2f}",
                "end": f"{segment.end:.2f}",
                "start_pct": f"{(100.0 * segment.start / summary.duration_seconds):.3f}" if summary.duration_seconds else "0",
                "width_pct": f"{(100.0 * max(segment.end - segment.start, 0.01) / summary.duration_seconds):.3f}" if summary.duration_seconds else "0",
            }
            for index, segment in enumerate(summary.segments)
        ]
        context["duration_seconds"] = f"{summary.duration_seconds:.2f}"
        tonal_text = (
            ", ".join(f"{hz:.0f} Hz" for hz in summary.tonal_lines_hz[:4])
            if summary.tonal_lines_hz
            else "no strong stationary tonal lines detected"
        )
        context["summary_line"] = (
            f"Detected {len(summary.segments) or 1} likely rumble region(s), "
            f"kept roughly {summary.elephant_band[0]}–{summary.elephant_band[1]} Hz, "
            f"and used a noise profile peaking near {summary.peak_noise_hz:.1f} Hz. "
            f"Tonal suppression target: {tonal_text}."
        )

    return render_template("index.html", **context)


@app.route("/downloads/<path:filename>")
def download_audio(filename: str):
    return send_file(OUTPUT_DIR / filename, as_attachment=False)


@app.route("/spectrograms/<path:filename>")
def spectrogram_asset(filename: str):
    return send_file(SPECTROGRAM_DIR / filename, as_attachment=False)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
