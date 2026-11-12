"""Simple JSON storage for watchlists, alert state and preferences."""
from __future__ import annotations

import json
import os
import threading
from typing import Any

MAX_SYMBOLS = 15


class Storage:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.wl_path = os.path.join(data_dir, "watchlists.json")
        self.seen_path = os.path.join(data_dir, "seen.json")
        os.makedirs(data_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._wl: dict[str, dict] = self._load(self.wl_path, {})
        self._seen: dict[str, dict] = self._load(self.seen_path, {})

    @staticmethod
    def _load(path: str, default: Any) -> Any:
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return default

    def _save_wl(self) -> None:
        with open(self.wl_path, "w", encoding="utf-8") as fh:
            json.dump(self._wl, fh, ensure_ascii=False, indent=1)

    def _save_seen(self) -> None:
        with open(self.seen_path, "w", encoding="utf-8") as fh:
            json.dump(self._seen, fh, ensure_ascii=False)

    # ------------------------------------------------------------ watchlist
    def chat(self, chat_id: int | str) -> dict:
        key = str(chat_id)
        return self._wl.setdefault(key, {"symbols": [], "alerts": True})

    def symbols(self, chat_id: int | str) -> list[dict]:
        return self.chat(chat_id).get("symbols", [])

    def all_chats(self) -> dict[str, dict]:
        return self._wl

    def add_symbol(self, chat_id: int | str, item: dict) -> tuple[bool, str]:
        """Returns (ok, error_code)."""
        with self._lock:
            data = self.chat(chat_id)
            syms = data["symbols"]
            if any(s["insCode"] == item["insCode"] for s in syms):
                return False, "duplicate"
            if len(syms) >= MAX_SYMBOLS:
                return False, "limit"
            syms.append(item)
            self._save_wl()
        return True, ""

    def remove_symbol(self, chat_id: int | str, ins_code: str) -> bool:
        with self._lock:
            data = self.chat(chat_id)
            before = len(data["symbols"])
            data["symbols"] = [s for s in data["symbols"] if s["insCode"] != ins_code]
            changed = len(data["symbols"]) != before
            if changed:
                self._save_wl()
        return changed

    def toggle_alerts(self, chat_id: int | str) -> bool:
        with self._lock:
            data = self.chat(chat_id)
            data["alerts"] = not data.get("alerts", True)
            self._save_wl()
        return data["alerts"]

    # ----------------------------------------------------------- alert state
    def seen_ids(self, chat_id: int | str, kind: str) -> set[str]:
        data = self._seen.setdefault(str(chat_id), {})
        return set(data.get(kind, []))

    def mark_seen(self, chat_id: int | str, kind: str, ids: list[str]) -> None:
        with self._lock:
            data = self._seen.setdefault(str(chat_id), {})
            arr = data.setdefault(kind, [])
            arr.extend(ids)
            del arr[:-300]  # keep last 300
            self._save_seen()

    def last_final_date(self, chat_id: int | str) -> str | None:
        return self._seen.get(str(chat_id), {}).get("final_date")

    def set_final_date(self, chat_id: int | str, date_str: str) -> None:
        with self._lock:
            data = self._seen.setdefault(str(chat_id), {})
            data["final_date"] = date_str
            self._save_seen()
