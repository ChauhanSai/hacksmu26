"""Flask routes for open-source audio contributions + Solana rewards."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, session
from werkzeug.utils import secure_filename

from contribute_store import ContributeStore
from solana_reward import send_sol_reward

ALLOWED_EXT = {".wav"}
MAX_CONTRIBUTE_BYTES = 80 * 1024 * 1024


def register_contribute_routes(app: Flask, base_dir: Path) -> None:
    store = ContributeStore(base_dir)
    reward_lamports = int(os.environ.get("REWARD_LAMPORTS", str(int(1.5 * 1e9))))

    @app.route("/api/contribute/ethogram-options", methods=["GET"])
    def contribute_ethogram_options():
        path = base_dir / "data" / "ethogram_options.json"
        if not path.is_file():
            return jsonify({"error": "Ethogram options file is missing."}), 503
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return jsonify({"error": f"Could not load ethogram options: {exc}"}), 500
        return jsonify(data)

    @app.route("/api/contribute/config", methods=["GET"])
    def contribute_config():
        return jsonify(
            {
                "rpcUrl": os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com"),
                "network": "devnet",
                "rewardLamports": reward_lamports,
                "rewardSol": round(reward_lamports / 1e9, 6),
                "treasuryConfigured": bool(os.environ.get("TREASURY_SECRET_KEY", "").strip()),
            }
        )

    @app.route("/api/contribute/wallet/<pubkey>/balance", methods=["GET"])
    def contribute_wallet_balance(pubkey: str):
        """SOL balance for a pubkey via configured RPC (devnet demo)."""
        try:
            from solders.pubkey import Pubkey
            from solana.rpc.api import Client

            pk = Pubkey.from_string(pubkey.strip())
        except Exception as exc:
            return jsonify({"error": f"Invalid pubkey: {exc}"}), 400
        rpc = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
        try:
            client = Client(rpc)
            resp = client.get_balance(pk)
            lamports = int(resp.value) if resp.value is not None else 0
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify(
            {
                "lamports": lamports,
                "sol": round(lamports / 1e9, 9),
                "network": "devnet",
                "rpcUrl": rpc,
            }
        )

    @app.route("/api/contribute/submit", methods=["POST"])
    def contribute_submit():
        wallet = (request.form.get("wallet") or "").strip()
        note = (request.form.get("note") or "").strip()
        sex = (request.form.get("sex") or "").strip()
        age = (request.form.get("age") or "").strip()
        situation = (request.form.get("situation") or "").strip()
        duration = (request.form.get("duration") or "").strip()
        duration_other = (request.form.get("durationOther") or "").strip()
        if duration == "__other__":
            duration = duration_other
        sound_segments = (request.form.get("soundSegments") or "").strip()
        ethogram_context = (request.form.get("ethogramContext") or "").strip()
        ethogram_name = (request.form.get("ethogramName") or "").strip()
        recording_mode = (request.form.get("recordingMode") or "").strip()
        audio = request.files.get("audio")

        if not wallet:
            return jsonify({"error": "Connect a Solana wallet first."}), 400
        if audio is None or audio.filename == "":
            return jsonify({"error": "Choose a WAV file."}), 400

        suffix = Path(audio.filename).suffix.lower()
        if suffix not in ALLOWED_EXT:
            return jsonify({"error": "Only .wav uploads are allowed."}), 400

        audio.stream.seek(0, os.SEEK_END)
        size = audio.stream.tell()
        audio.stream.seek(0)
        if size > MAX_CONTRIBUTE_BYTES:
            return jsonify({"error": "File too large (max 80 MB)."}), 400

        if not ethogram_context or not ethogram_name:
            return jsonify({"error": "Choose ethogram context and call / behavior name."}), 400
        if not recording_mode:
            return jsonify({"error": "Choose recording mode."}), 400
        if not duration:
            return jsonify({"error": "Choose or enter duration."}), 400

        safe = secure_filename(audio.filename)
        submission = store.add(
            wallet=wallet,
            original_name=safe,
            note=note,
            sex=sex,
            age=age,
            situation=situation,
            duration=duration,
            sound_segments=sound_segments,
            ethogram_context=ethogram_context,
            ethogram_name=ethogram_name,
            recording_mode=recording_mode,
            reward_lamports=reward_lamports,
        )
        path = store.upload_dir / submission.stored_name
        audio.save(str(path))

        return jsonify(
            {
                "ok": True,
                "submission": {
                    "id": submission.id,
                    "status": submission.status,
                    "submittedAt": submission.submitted_at,
                },
            }
        )

    @app.route("/api/contribute/biologist/login", methods=["POST"])
    def contribute_bio_login():
        data = request.get_json(silent=True) or {}
        # Demo: any username/password (or omitted) is accepted
        raw_user = (data.get("username") or "").strip()
        display = raw_user if raw_user else "Reviewer"
        session["bio"] = True
        session["bio_user"] = display
        session.permanent = True
        return jsonify({"ok": True, "username": display})

    @app.route("/api/contribute/biologist/logout", methods=["POST"])
    def contribute_bio_logout():
        session.pop("bio", None)
        return jsonify({"ok": True})

    @app.route("/api/contribute/biologist/me", methods=["GET"])
    def contribute_bio_me():
        if not session.get("bio"):
            return jsonify({"loggedIn": False})
        return jsonify({"loggedIn": True, "username": session.get("bio_user") or "Reviewer"})

    @app.route("/api/contribute/biologist/submissions", methods=["GET"])
    def contribute_bio_list():
        if not session.get("bio"):
            return jsonify({"error": "Unauthorized."}), 401
        rows = []
        for s in store.list_all():
            rows.append(
                {
                    "id": s.id,
                    "wallet": s.wallet,
                    "originalName": s.original_name,
                    "note": s.note,
                    "sex": s.sex,
                    "age": s.age,
                    "situation": s.situation,
                    "duration": s.duration,
                    "soundSegments": s.sound_segments,
                    "ethogramContext": s.ethogram_context,
                    "ethogramName": s.ethogram_name,
                    "recordingMode": s.recording_mode,
                    "status": s.status,
                    "submittedAt": s.submitted_at,
                    "reviewedAt": s.reviewed_at,
                    "txSignature": s.tx_signature,
                    "rewardSol": s.reward_lamports / 1e9,
                    "rewardLamports": s.reward_lamports,
                }
            )
        return jsonify({"submissions": rows})

    @app.route("/api/contribute/biologist/review/<sid>", methods=["POST"])
    def contribute_bio_review(sid: str):
        if not session.get("bio"):
            return jsonify({"error": "Unauthorized."}), 401
        data = request.get_json(silent=True) or {}
        action = (data.get("action") or "").strip().lower()
        if action not in ("accept", "reject"):
            return jsonify({"error": "action must be accept or reject."}), 400

        sub = store.get(sid)
        if not sub:
            return jsonify({"error": "Not found."}), 404
        if sub.status != "pending":
            return jsonify({"error": f"Already {sub.status}."}), 400

        now = datetime.now(timezone.utc).isoformat()

        if action == "reject":
            sub.status = "rejected"
            sub.reviewed_at = now
            store.update(sub)
            return jsonify({"ok": True, "status": "rejected"})

        # Accept: prefer client-signed transfer (biologist Phantom wallet → contributor)
        client_sig = (data.get("txSignature") or "").strip()
        if client_sig:
            sub.status = "accepted"
            sub.reviewed_at = now
            sub.tx_signature = client_sig
            store.update(sub)
            return jsonify({"ok": True, "status": "accepted", "txSignature": client_sig})

        tx_sig, err = send_sol_reward(
            sub.wallet,
            sub.reward_lamports,
            rpc_url=os.environ.get("SOLANA_RPC_URL"),
            treasury_secret_b58=os.environ.get("TREASURY_SECRET_KEY"),
        )
        if err:
            return jsonify(
                {
                    "error": f"Payout failed: {err}. "
                    "Connect the biologist wallet in Phantom and approve the transfer, "
                    "or set TREASURY_SECRET_KEY for server-side payout.",
                }
            ), 500

        sub.status = "accepted"
        sub.reviewed_at = now
        sub.tx_signature = tx_sig
        store.update(sub)
        return jsonify({"ok": True, "status": "accepted", "txSignature": tx_sig})

    @app.route("/api/contribute/file/<sid>", methods=["GET"])
    def contribute_file(sid: str):
        if not session.get("bio"):
            return jsonify({"error": "Unauthorized."}), 401
        sub = store.get(sid)
        if not sub:
            abort(404)
        path = store.upload_dir / sub.stored_name
        if not path.is_file():
            abort(404)
        return send_file(path, mimetype="audio/wav", as_attachment=False)
