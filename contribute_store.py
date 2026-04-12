"""JSON-backed store for open-source audio contributions (demo)."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename


@dataclass
class Submission:
    id: str
    wallet: str
    original_name: str
    stored_name: str
    note: str
    sex: str
    age: str
    situation: str
    duration: str
    sound_segments: str
    ethogram_context: str
    ethogram_name: str
    recording_mode: str
    status: str  # pending | accepted | rejected
    submitted_at: str
    reviewed_at: str | None
    tx_signature: str | None
    reward_lamports: int

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Submission:
        return cls(
            id=d["id"],
            wallet=d["wallet"],
            original_name=d["original_name"],
            stored_name=d["stored_name"],
            note=d.get("note") or "",
            sex=(d.get("sex") or "")[:120],
            age=(d.get("age") or "")[:120],
            situation=(d.get("situation") or "")[:2000],
            duration=(d.get("duration") or "")[:200],
            sound_segments=(d.get("sound_segments") or "")[:4000],
            ethogram_context=(d.get("ethogram_context") or "")[:500],
            ethogram_name=(d.get("ethogram_name") or "")[:500],
            recording_mode=(d.get("recording_mode") or "")[:120],
            status=d["status"],
            submitted_at=d["submitted_at"],
            reviewed_at=d.get("reviewed_at"),
            tx_signature=d.get("tx_signature"),
            reward_lamports=int(d.get("reward_lamports", 0)),
        )


_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ContributeStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.data_path = self.base_dir / "data" / "contribute_submissions.json"
        self.upload_dir = self.base_dir / "contribute_uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_path.is_file():
            self._write_raw({"submissions": []})

    def _read_raw(self) -> dict[str, Any]:
        if not self.data_path.is_file():
            return {"submissions": []}
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    def _write_raw(self, data: dict[str, Any]) -> None:
        self.data_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_all(self) -> list[Submission]:
        raw = self._read_raw()
        return [Submission.from_json(x) for x in raw.get("submissions", [])]

    def get(self, sid: str) -> Submission | None:
        for s in self.list_all():
            if s.id == sid:
                return s
        return None

    def add(
        self,
        *,
        wallet: str,
        original_name: str,
        note: str,
        sex: str = "",
        age: str = "",
        situation: str = "",
        duration: str = "",
        sound_segments: str = "",
        ethogram_context: str = "",
        ethogram_name: str = "",
        recording_mode: str = "",
        reward_lamports: int,
    ) -> Submission:
        sid = uuid.uuid4().hex
        safe = secure_filename(original_name) or "recording.wav"
        stored_name = f"{sid}_{safe}"
        sub = Submission(
            id=sid,
            wallet=wallet.strip(),
            original_name=original_name,
            stored_name=stored_name,
            note=note.strip()[:2000],
            sex=sex.strip()[:120],
            age=age.strip()[:120],
            situation=situation.strip()[:2000],
            duration=duration.strip()[:200],
            sound_segments=sound_segments.strip()[:4000],
            ethogram_context=ethogram_context.strip()[:500],
            ethogram_name=ethogram_name.strip()[:500],
            recording_mode=recording_mode.strip()[:120],
            status="pending",
            submitted_at=_utc_now(),
            reviewed_at=None,
            tx_signature=None,
            reward_lamports=reward_lamports,
        )
        with _lock:
            data = self._read_raw()
            data.setdefault("submissions", []).append(sub.to_json())
            self._write_raw(data)
        return sub

    def update(self, sub: Submission) -> None:
        with _lock:
            data = self._read_raw()
            subs = data.get("submissions", [])
            for i, row in enumerate(subs):
                if row.get("id") == sub.id:
                    subs[i] = sub.to_json()
                    self._write_raw(data)
                    return
        raise KeyError(sub.id)
