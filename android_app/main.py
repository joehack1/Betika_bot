from __future__ import annotations

import threading
from typing import Any

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout


KV = """
<RootWidget>:
    orientation: "vertical"
    padding: dp(10)
    spacing: dp(8)

    Label:
        text: "Betika Bot Mobile"
        size_hint_y: None
        height: dp(36)
        bold: True

    BoxLayout:
        orientation: "vertical"
        size_hint_y: None
        height: self.minimum_height
        spacing: dp(4)

        Label:
            text: "Server URL"
            size_hint_y: None
            height: dp(20)
            halign: "left"
            text_size: self.width, None
        TextInput:
            id: server_url
            text: "http://192.168.1.10:8787"
            multiline: False
            size_hint_y: None
            height: dp(42)

        Label:
            text: "Odds Limit (max)"
            size_hint_y: None
            height: dp(20)
            halign: "left"
            text_size: self.width, None
        TextInput:
            id: max_odds
            text: "1.35"
            multiline: False
            input_filter: "float"
            size_hint_y: None
            height: dp(42)

        Label:
            text: "Min Odds"
            size_hint_y: None
            height: dp(20)
            halign: "left"
            text_size: self.width, None
        TextInput:
            id: min_odds
            text: "1.01"
            multiline: False
            input_filter: "float"
            size_hint_y: None
            height: dp(42)

        Label:
            text: "No. of Selections"
            size_hint_y: None
            height: dp(20)
            halign: "left"
            text_size: self.width, None
        TextInput:
            id: count
            text: "39"
            multiline: False
            input_filter: "int"
            size_hint_y: None
            height: dp(42)

        Label:
            text: "Stake (KES)"
            size_hint_y: None
            height: dp(20)
            halign: "left"
            text_size: self.width, None
        TextInput:
            id: stake
            text: "2"
            multiline: False
            input_filter: "float"
            size_hint_y: None
            height: dp(42)

    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(12)
        Label:
            text: "Live Bet (--execute)"
            halign: "left"
            text_size: self.width, None
        Switch:
            id: execute
            active: False
            size_hint_x: None
            width: dp(56)

    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(12)
        Label:
            text: "Keep Browser Open"
            halign: "left"
            text_size: self.width, None
        Switch:
            id: keep_open
            active: True
            size_hint_x: None
            width: dp(56)

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        spacing: dp(8)
        Button:
            text: "Start Bot"
            on_release: app.start_bot()
        Button:
            text: "Stop"
            on_release: app.stop_bot()
        Button:
            text: "Refresh"
            on_release: app.fetch_logs()

    Label:
        id: status
        text: "Idle"
        size_hint_y: None
        height: dp(24)
        halign: "left"
        text_size: self.width, None

    Label:
        text: "Output"
        size_hint_y: None
        height: dp(24)
        halign: "left"
        text_size: self.width, None

    ScrollView:
        bar_width: dp(6)
        Label:
            id: output
            text: ""
            size_hint_y: None
            height: max(self.texture_size[1], self.parent.height if self.parent else 0)
            text_size: self.width, None
            valign: "top"
            halign: "left"
"""


class RootWidget(BoxLayout):
    pass


class BetikaMobileApp(App):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.log_buffer: list[str] = []
        self.log_cursor = 0
        self.poll_event = None

    def build(self) -> RootWidget:
        Builder.load_string(KV)
        return RootWidget()

    def on_start(self) -> None:
        self.poll_event = Clock.schedule_interval(lambda *_: self.fetch_logs(), 2.0)
        self.fetch_health()

    def on_stop(self) -> None:
        if self.poll_event is not None:
            self.poll_event.cancel()
            self.poll_event = None

    def start_bot(self) -> None:
        payload = self._collect_payload()
        if payload is None:
            return
        self._request_async("POST", "/start", payload, self._on_start_response)

    def stop_bot(self) -> None:
        self._request_async("POST", "/stop", {}, self._on_stop_response)

    def fetch_logs(self) -> None:
        self._request_async("GET", f"/logs?from={self.log_cursor}", None, self._on_logs_response)

    def fetch_health(self) -> None:
        self._request_async("GET", "/health", None, self._on_health_response)

    def _collect_payload(self) -> dict[str, Any] | None:
        ids = self.root.ids
        try:
            payload = {
                "max_odds": float(ids.max_odds.text.strip()),
                "min_odds": float(ids.min_odds.text.strip()),
                "count": int(ids.count.text.strip()),
                "stake": float(ids.stake.text.strip()),
                "execute": bool(ids.execute.active),
                "keep_open": bool(ids.keep_open.active),
            }
        except ValueError:
            self._append_log("Invalid numeric input.")
            self._set_status("Validation failed")
            return None

        if payload["count"] <= 0 or payload["stake"] <= 0:
            self._append_log("Count and stake must be greater than 0.")
            self._set_status("Validation failed")
            return None
        if payload["min_odds"] <= 0 or payload["max_odds"] <= 0:
            self._append_log("Odds must be greater than 0.")
            self._set_status("Validation failed")
            return None
        if payload["min_odds"] > payload["max_odds"]:
            self._append_log("Min odds cannot be greater than max odds.")
            self._set_status("Validation failed")
            return None

        return payload

    def _server_url(self) -> str:
        return self.root.ids.server_url.text.strip().rstrip("/")

    def _request_async(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        callback: Any,
    ) -> None:
        base = self._server_url()
        if not base:
            self._set_status("Server URL is required")
            return

        def worker() -> None:
            url = f"{base}{path}"
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=payload,
                    timeout=10,
                )
                try:
                    data = response.json()
                except ValueError:
                    data = {}

                if response.ok:
                    Clock.schedule_once(lambda *_: callback(True, data, None))
                    return

                message = "Request failed."
                if isinstance(data, dict):
                    message = str(data.get("error") or data.get("message") or message)
                else:
                    message = f"HTTP {response.status_code}"
                Clock.schedule_once(lambda *_: callback(False, data, message))
            except requests.RequestException as exc:
                Clock.schedule_once(lambda *_: callback(False, None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_start_response(self, ok: bool, data: dict[str, Any] | None, error: str | None) -> None:
        if not ok:
            self._append_log(f"Start failed: {error}")
            self._set_status("Start failed")
            return
        message = str(data.get("message", "Start requested.")) if data else "Start requested."
        self._append_log(message)
        self._set_status("Running" if data and data.get("running") else "Idle")

    def _on_stop_response(self, ok: bool, data: dict[str, Any] | None, error: str | None) -> None:
        if not ok:
            self._append_log(f"Stop failed: {error}")
            self._set_status("Stop failed")
            return
        message = str(data.get("message", "Stop requested.")) if data else "Stop requested."
        self._append_log(message)
        self._set_status("Running" if data and data.get("running") else "Idle")

    def _on_logs_response(self, ok: bool, data: dict[str, Any] | None, error: str | None) -> None:
        if not ok:
            self._set_status("Logs unavailable")
            return
        if not data:
            return
        lines = data.get("lines", [])
        if isinstance(lines, list):
            for line in lines:
                self._append_log(str(line))
        self.log_cursor = int(data.get("next_index", self.log_cursor))
        self._set_status("Running" if data.get("running") else "Idle")

    def _on_health_response(self, ok: bool, data: dict[str, Any] | None, error: str | None) -> None:
        if not ok:
            self._set_status("Server unreachable")
            self._append_log(f"Health check failed: {error}")
            return
        if not data:
            return
        self._set_status("Running" if data.get("running") else "Idle")

    def _append_log(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        self.log_buffer.append(line)
        if len(self.log_buffer) > 600:
            overflow = len(self.log_buffer) - 600
            del self.log_buffer[:overflow]
        self.root.ids.output.text = "\n".join(self.log_buffer)

    def _set_status(self, text: str) -> None:
        self.root.ids.status.text = text


if __name__ == "__main__":
    BetikaMobileApp().run()
