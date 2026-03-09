from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Callable


APP_TITLE = "Betika Bot GUI"
COLORS = {
    "bg": "#031015",
    "panel": "#071a20",
    "panel_alt": "#0a232b",
    "panel_deep": "#020a0d",
    "line": "#12353f",
    "text": "#d3fbff",
    "muted": "#73b0b7",
    "accent": "#77f7ff",
    "accent_soft": "#2dbec7",
    "warn": "#ffb86f",
    "danger": "#ff7272",
    "success": "#7efab0",
}
FONT_FAMILY = "Consolas"


class BetikaGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1024x720")
        self.root.minsize(920, 640)
        self.root.configure(bg=COLORS["bg"])

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.reader_thread: threading.Thread | None = None

        self.script_path = Path(__file__).resolve().with_name("betika.py")

        self.typing_queue: list[tuple[str, str]] = []
        self.active_log_text = ""
        self.active_log_tag = "log"
        self.active_log_index = 0
        self.typing_active = False

        self.header_target = ""
        self.header_index = 0
        self.header_done_callback: Callable[[], None] | None = None
        self.cursor_visible = True
        self.sweep_position = 0

        self.status_var = tk.StringVar(value="INITIALIZING")
        self.init_var = tk.StringVar(value="")
        self.clock_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="SIMULATION")
        self.process_var = tk.StringVar(value="OFFLINE")
        self.channel_var = tk.StringVar(value="SECURE-LINK")

        self._build_ui()
        self._schedule_log_poll()
        self._schedule_clock()
        self._blink_cursor()
        self._animate_header(
            "INITIALIZING SECURE OPERATIONS CONSOLE",
            callback=self._start_boot_sequence,
        )
        self._animate_signal_sweep()

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["bg"])
        shell.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        shell.grid_columnconfigure(0, weight=3)
        shell.grid_columnconfigure(1, weight=5)
        shell.grid_rowconfigure(1, weight=1)

        header = self._panel(shell, accent=COLORS["accent"])
        header.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 14))
        header.grid_columnconfigure(0, weight=4)
        header.grid_columnconfigure(1, weight=2)

        brand_frame = tk.Frame(header, bg=COLORS["panel"])
        brand_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        tk.Label(
            brand_frame,
            text="BETIKA // FIELD TERMINAL",
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            font=(FONT_FAMILY, 24, "bold"),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            brand_frame,
            textvariable=self.init_var,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=(FONT_FAMILY, 11),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 10))
        metrics = tk.Frame(brand_frame, bg=COLORS["panel"])
        metrics.pack(fill=tk.X)
        self._metric(metrics, "STATE", self.status_var).pack(side=tk.LEFT, padx=(0, 12))
        self._metric(metrics, "MODE", self.mode_var).pack(side=tk.LEFT, padx=(0, 12))
        self._metric(metrics, "PROCESS", self.process_var).pack(side=tk.LEFT, padx=(0, 12))
        self._metric(metrics, "CHANNEL", self.channel_var).pack(side=tk.LEFT)

        signal_frame = tk.Frame(header, bg=COLORS["panel"])
        signal_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        tk.Label(
            signal_frame,
            textvariable=self.clock_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(FONT_FAMILY, 10),
            anchor="e",
        ).pack(fill=tk.X)
        self.signal_canvas = tk.Canvas(
            signal_frame,
            width=300,
            height=110,
            bg=COLORS["panel_deep"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            bd=0,
        )
        self.signal_canvas.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._draw_signal_panel()

        controls = self._panel(shell, accent=COLORS["accent_soft"])
        controls.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_rowconfigure(2, weight=1)

        tk.Label(
            controls,
            text="RUN PROFILE",
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            font=(FONT_FAMILY, 14, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
        tk.Label(
            controls,
            text="Tune the bot launch parameters before deploying the process.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(FONT_FAMILY, 9),
            justify=tk.LEFT,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        inputs = tk.Frame(controls, bg=COLORS["panel"])
        inputs.grid(row=2, column=0, sticky="nsew", padx=16)
        inputs.grid_columnconfigure(0, weight=1)
        inputs.grid_columnconfigure(1, weight=1)

        self.max_odds_var = tk.StringVar(value="1.35")
        self.count_var = tk.StringVar(value="39")
        self.stake_var = tk.StringVar(value="2")
        self.min_odds_var = tk.StringVar(value="1.01")
        self.execute_var = tk.BooleanVar(value=False)
        self.keep_open_var = tk.BooleanVar(value=True)

        self._field(inputs, "ODDS LIMIT // MAX", self.max_odds_var, 0, 0)
        self._field(inputs, "SELECTION COUNT", self.count_var, 0, 1)
        self._field(inputs, "STAKE // KES", self.stake_var, 1, 0)
        self._field(inputs, "ODDS FLOOR // MIN", self.min_odds_var, 1, 1)

        toggles = tk.Frame(controls, bg=COLORS["panel"])
        toggles.grid(row=3, column=0, sticky="ew", padx=16, pady=(10, 0))
        self._toggle(toggles, "EXECUTE LIVE BET", self.execute_var, self._sync_mode).pack(
            fill=tk.X, pady=(0, 8)
        )
        self._toggle(toggles, "KEEP BROWSER OPEN", self.keep_open_var).pack(fill=tk.X)

        actions = tk.Frame(controls, bg=COLORS["panel"])
        actions.grid(row=4, column=0, sticky="ew", padx=16, pady=(14, 16))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        actions.grid_columnconfigure(2, weight=1)

        self.run_btn = self._action_button(
            actions,
            text="START RUN",
            command=self.start_run,
            fill=COLORS["accent"],
            fg=COLORS["panel_deep"],
        )
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.stop_btn = self._action_button(
            actions,
            text="HALT",
            command=self.stop_run,
            fill=COLORS["danger"],
            fg=COLORS["panel_deep"],
            state=tk.DISABLED,
        )
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=4)

        clear_btn = self._action_button(
            actions,
            text="PURGE LOG",
            command=self.clear_log,
            fill=COLORS["panel_alt"],
            fg=COLORS["text"],
        )
        clear_btn.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        console = self._panel(shell, accent=COLORS["line"])
        console.grid(row=1, column=1, sticky="nsew")
        console.grid_rowconfigure(2, weight=1)
        console.grid_columnconfigure(0, weight=1)

        tk.Label(
            console,
            text="LIVE CONSOLE",
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            font=(FONT_FAMILY, 14, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        tk.Label(
            console,
            text="Typed operator feed. Runtime output streams in with delayed character rendering.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(FONT_FAMILY, 9),
            justify=tk.LEFT,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        log_frame = tk.Frame(console, bg=COLORS["panel"])
        log_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap=tk.WORD,
            bg=COLORS["panel_deep"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            padx=12,
            pady=12,
            font=(FONT_FAMILY, 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(
            log_frame,
            orient=tk.VERTICAL,
            command=self.log_text.yview,
            troughcolor=COLORS["panel_deep"],
            bg=COLORS["panel_alt"],
            activebackground=COLORS["accent_soft"],
            relief=tk.FLAT,
            bd=0,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set, state=tk.DISABLED)
        self._configure_log_tags()

    def _panel(self, parent: tk.Misc, accent: str) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=COLORS["panel"],
            highlightthickness=1,
            highlightbackground=accent,
            bd=0,
        )

    def _metric(self, parent: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(
            parent,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            padx=10,
            pady=8,
        )
        tk.Label(
            frame,
            text=label,
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            font=(FONT_FAMILY, 8),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            frame,
            textvariable=variable,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            font=(FONT_FAMILY, 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))
        return frame

    def _field(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.StringVar,
        row: int,
        column: int,
    ) -> None:
        cell = tk.Frame(
            parent,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            padx=10,
            pady=10,
        )
        cell.grid(row=row, column=column, sticky="ew", padx=(0, 10 if column == 0 else 0), pady=(0, 10))
        tk.Label(
            cell,
            text=label,
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            font=(FONT_FAMILY, 8),
            anchor="w",
        ).pack(fill=tk.X)
        entry = tk.Entry(
            cell,
            textvariable=variable,
            bg=COLORS["panel_deep"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=(FONT_FAMILY, 14),
        )
        entry.pack(fill=tk.X, pady=(8, 0), ipady=8)

    def _toggle(
        self,
        parent: tk.Misc,
        text: str,
        variable: tk.BooleanVar,
        command: Callable[[], None] | None = None,
    ) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            selectcolor=COLORS["panel_alt"],
            activebackground=COLORS["panel_alt"],
            activeforeground=COLORS["accent"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            padx=12,
            pady=10,
            relief=tk.FLAT,
            bd=0,
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        )

    def _action_button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        fill: str,
        fg: str,
        state: str = tk.NORMAL,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            state=state,
            bg=fill,
            fg=fg,
            activebackground=COLORS["warn"] if fill == COLORS["accent"] else fill,
            activeforeground=COLORS["panel_deep"] if fill != COLORS["panel_alt"] else COLORS["text"],
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=10,
            disabledforeground="#6a8b90",
            font=(FONT_FAMILY, 10, "bold"),
            cursor="hand2",
        )

    def _configure_log_tags(self) -> None:
        self.log_text.tag_configure("system", foreground=COLORS["accent"])
        self.log_text.tag_configure("warn", foreground=COLORS["warn"])
        self.log_text.tag_configure("error", foreground=COLORS["danger"])
        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("log", foreground=COLORS["text"])
        self.log_text.tag_configure("muted", foreground=COLORS["muted"])

    def _draw_signal_panel(self) -> None:
        width = 300
        height = 110
        for x in range(0, width + 1, 30):
            self.signal_canvas.create_line(x, 0, x, height, fill="#0b2d36")
        for y in range(0, height + 1, 22):
            self.signal_canvas.create_line(0, y, width, y, fill="#0b2d36")

        waveform = [
            6, 18, 18, 22, 36, 28, 60, 56, 84, 34, 110, 70, 132, 22, 150, 52,
            174, 44, 196, 86, 214, 30, 232, 38, 252, 58, 274, 52, 294, 64,
        ]
        self.signal_canvas.create_line(
            *waveform,
            fill=COLORS["accent"],
            width=2,
            smooth=True,
        )
        self.signal_canvas.create_text(
            12,
            12,
            text="SIGNAL ARRAY // BOT TELEMETRY",
            anchor="nw",
            fill=COLORS["muted"],
            font=(FONT_FAMILY, 8),
        )
        self.sweep_line = self.signal_canvas.create_line(
            0,
            0,
            0,
            height,
            fill=COLORS["accent_soft"],
            width=2,
        )

    def _animate_signal_sweep(self) -> None:
        self.sweep_position = (self.sweep_position + 5) % 300
        self.signal_canvas.coords(self.sweep_line, self.sweep_position, 0, self.sweep_position, 110)
        self.root.after(45, self._animate_signal_sweep)

    def _schedule_clock(self) -> None:
        now = datetime.now()
        self.clock_var.set(now.strftime("%d %b %Y // %H:%M:%S"))
        self.root.after(1000, self._schedule_clock)

    def _blink_cursor(self) -> None:
        self.cursor_visible = not self.cursor_visible
        rendered = self.header_target[: self.header_index]
        suffix = " _" if self.cursor_visible and self.header_index < len(self.header_target) else ""
        self.init_var.set(rendered + suffix)
        self.root.after(320, self._blink_cursor)

    def _animate_header(self, text: str, callback: Callable[[], None] | None = None) -> None:
        self.header_target = text
        self.header_index = 0
        self.header_done_callback = callback
        self.init_var.set("")
        self._step_header_animation()

    def _step_header_animation(self) -> None:
        if self.header_index < len(self.header_target):
            self.header_index += 1
            self.init_var.set(self.header_target[: self.header_index] + " _")
            self.root.after(34, self._step_header_animation)
            return

        self.init_var.set(self.header_target)
        if self.header_done_callback is not None:
            callback = self.header_done_callback
            self.header_done_callback = None
            self.root.after(180, callback)

    def _start_boot_sequence(self) -> None:
        for delay, line in (
            (80, "BOOTSTRAP//UI skin loaded"),
            (260, "HANDSHAKE//secure operator channel online"),
            (520, "TELEMETRY//typed console feed armed"),
            (760, "READY//awaiting launch parameters"),
        ):
            self.root.after(delay, lambda message=line: self._append_log(message + "\n", "system"))

        self.root.after(920, lambda: self.status_var.set("STANDBY"))
        self.root.after(920, lambda: self.process_var.set("READY"))
        self._sync_mode()

    def _sync_mode(self) -> None:
        self.mode_var.set("LIVE EXECUTION" if self.execute_var.get() else "SIMULATION")

    def start_run(self) -> None:
        if self.process is not None:
            self._append_log("SESSION BUSY//a run is already active\n", "warn")
            return

        try:
            max_odds = float(self.max_odds_var.get().strip())
            min_odds = float(self.min_odds_var.get().strip())
            count = int(self.count_var.get().strip())
            stake = float(self.stake_var.get().strip())
        except ValueError:
            self._append_log("VALIDATION ERROR//numeric inputs are malformed\n", "error")
            return

        if count <= 0:
            self._append_log("VALIDATION ERROR//selection count must be greater than zero\n", "error")
            return
        if stake <= 0:
            self._append_log("VALIDATION ERROR//stake must be greater than zero\n", "error")
            return
        if min_odds <= 0 or max_odds <= 0:
            self._append_log("VALIDATION ERROR//odds values must be positive\n", "error")
            return
        if min_odds > max_odds:
            self._append_log("VALIDATION ERROR//min odds exceed max odds limit\n", "error")
            return
        if not self.script_path.exists():
            self._append_log(f"LAUNCH ERROR//missing script: {self.script_path.name}\n", "error")
            return

        cmd = [
            sys.executable,
            str(self.script_path),
            "--max-odds",
            f"{max_odds}",
            "--min-odds",
            f"{min_odds}",
            "--count",
            str(count),
            "--stake",
            f"{stake}",
        ]

        if self.execute_var.get():
            cmd.append("--execute")
        if self.keep_open_var.get():
            cmd.append("--keep-open")

        self._append_log(f"LAUNCH//{' '.join(cmd)}\n", "system")

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.script_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self._append_log(f"LAUNCH ERROR//{exc}\n", "error")
            self.process = None
            return

        self.run_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.status_var.set("RUNNING")
        self.process_var.set("ACTIVE")
        self._append_log("PROCESS//betting engine deployed\n", "success")

        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()

    def stop_run(self) -> None:
        if self.process is None:
            self._append_log("PROCESS//no active run to halt\n", "muted")
            return

        self._append_log("HALT SIGNAL//terminating active process\n", "warn")
        self.process.terminate()

    def clear_log(self) -> None:
        self.typing_queue.clear()
        self.active_log_text = ""
        self.active_log_index = 0
        self.typing_active = False
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _read_output(self) -> None:
        assert self.process is not None
        proc = self.process

        if proc.stdout is not None:
            for line in proc.stdout:
                self.log_queue.put(line)

        return_code = proc.wait()
        self.log_queue.put(f"\nPROCESS EXIT//code {return_code}\n")
        self.log_queue.put("__RUN_FINISHED__")

    def _schedule_log_poll(self) -> None:
        self.root.after(80, self._poll_log_queue)

    def _poll_log_queue(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg == "__RUN_FINISHED__":
                    self.process = None
                    self.reader_thread = None
                    self.run_btn.configure(state=tk.NORMAL)
                    self.stop_btn.configure(state=tk.DISABLED)
                    self.status_var.set("STANDBY")
                    self.process_var.set("READY")
                else:
                    self._append_log(msg)
        except queue.Empty:
            pass
        finally:
            self._schedule_log_poll()

    def _append_log(self, text: str, tag: str | None = None) -> None:
        resolved_tag = tag or self._infer_tag(text)
        self.typing_queue.append((text, resolved_tag))
        if not self.typing_active:
            self.typing_active = True
            self.root.after(6, self._type_log_step)

    def _type_log_step(self) -> None:
        if self.active_log_index >= len(self.active_log_text):
            if not self.typing_queue:
                self.typing_active = False
                self.active_log_text = ""
                return
            self.active_log_text, self.active_log_tag = self.typing_queue.pop(0)
            self.active_log_index = 0

        backlog = len(self.typing_queue)
        chunk_size = 1 if backlog < 4 else 3 if backlog < 12 else 6
        chunk = self.active_log_text[self.active_log_index : self.active_log_index + chunk_size]
        self.active_log_index += len(chunk)

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, chunk, self.active_log_tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

        delay = 7 if backlog < 4 else 3
        self.root.after(delay, self._type_log_step)

    def _infer_tag(self, text: str) -> str:
        lowered = text.lower()
        if "process exit//code" in lowered:
            return "success" if lowered.strip().endswith("0") else "error"
        if any(token in lowered for token in ("error", "failed", "traceback", "invalid")):
            return "error"
        if any(token in lowered for token in ("warning", "stopping", "halt", "busy")):
            return "warn"
        if any(token in lowered for token in ("exit", "completed", "ready", "deployed")):
            return "success"
        if any(token in lowered for token in ("starting", "launch", "boot", "handshake", "telemetry")):
            return "system"
        return "log"


def main() -> int:
    root = tk.Tk()
    app = BetikaGui(root)

    def on_close() -> None:
        if app.process is not None:
            app.stop_run()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
