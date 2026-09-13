"""CLI and runtime: capture → heat → pill / tray / text."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from dataclasses import dataclass, field, replace

from madlite import __version__
from madlite.audio import (
    CaptureError,
    DemoCapture,
    MonitorSource,
    discover_monitor,
    list_monitor_sources,
    open_capture,
)
from madlite.heat import HeatClassifier, HeatConfig, HeatLevel, HeatSample


@dataclass
class Runtime:
    listening: bool = True
    stop: bool = False
    level: HeatLevel = HeatLevel.CALM
    sample: HeatSample | None = None
    source_label: str = ""
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> tuple[bool, HeatLevel, HeatSample | None, str | None]:
        with self.lock:
            return self.listening, self.level, self.sample, self.error

    def set_listening(self, value: bool) -> None:
        with self.lock:
            self.listening = value
            if not value:
                self.level = HeatLevel.CALM
                self.sample = None

    def request_stop(self) -> None:
        with self.lock:
            self.stop = True
            self.listening = False

    def stopped(self) -> bool:
        with self.lock:
            return self.stop


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="madlite",
        description=(
            "Mad Lite — Meeting Atmosphere Dial. Local RMS/slope heat pill. "
            "Captures the default sink monitor (headphones or speakers), never the cloud."
        ),
    )
    p.add_argument("--version", action="version", version=f"madlite {__version__}")
    p.add_argument(
        "--list-sources",
        action="store_true",
        help="list sink monitor / loopback sources and exit",
    )
    p.add_argument(
        "--source",
        metavar="NAME",
        help="Pulse/PipeWire source name (must be a .monitor unless --allow-mic)",
    )
    p.add_argument(
        "--allow-mic",
        action="store_true",
        help="allow a non-monitor source (not the default; privacy footgun)",
    )
    p.add_argument(
        "--backend",
        choices=("auto", "soundcard", "parec", "pw-record"),
        default="auto",
        help="capture backend (auto tries soundcard, then parec, then pw-record)",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="synthetic energy loop; no audio device",
    )
    p.add_argument(
        "--text",
        action="store_true",
        help="print heat on stdout instead of (or as well as) GUI if GUI fails",
    )
    p.add_argument("--no-pill", action="store_true", help="do not open the Tk pill")
    p.add_argument("--no-tray", action="store_true", help="do not start the tray icon")
    p.add_argument("--rising-rms", type=float, default=None)
    p.add_argument("--hot-rms", type=float, default=None)
    p.add_argument("--rising-slope", type=float, default=None)
    return p


def _config_from_args(args: argparse.Namespace) -> HeatConfig:
    cfg = HeatConfig()
    updates = {}
    if args.rising_rms is not None:
        updates["rising_rms"] = args.rising_rms
    if args.hot_rms is not None:
        updates["hot_rms"] = args.hot_rms
    if args.rising_slope is not None:
        updates["rising_slope"] = args.rising_slope
    return replace(cfg, **updates) if updates else cfg


def _print_sources() -> int:
    try:
        current = discover_monitor()
        print(f"default monitor: {current.pulse_name}  ({current.label}, via {current.via})")
    except Exception as exc:
        print(f"default monitor: unavailable ({exc})", file=sys.stderr)
        current = None
    sources = list_monitor_sources()
    if not sources:
        print("no monitor sources found (is PipeWire/Pulse running?)")
        return 1
    print("monitors:")
    for src in sources:
        mark = " *" if current and src.pulse_name == current.pulse_name else ""
        print(f"  {src.pulse_name}{mark}")
        if src.label != src.pulse_name:
            print(f"      {src.label}  [{src.via}]")
    print("\n* default. Headphones work when they are the default sink.")
    return 0


def _audio_loop(runtime: Runtime, config: HeatConfig, source: MonitorSource, backend: str) -> None:
    classifier = HeatClassifier(config)
    capture = None
    try:
        while not runtime.stopped():
            with runtime.lock:
                listening = runtime.listening
            if not listening:
                if capture is not None:
                    capture.close()
                    capture = None
                    classifier.reset()
                time.sleep(0.05)
                continue
            if capture is None:
                try:
                    capture = open_capture(source, config, backend=backend)
                    with runtime.lock:
                        runtime.source_label = capture.source.label
                        runtime.error = None
                except CaptureError as exc:
                    with runtime.lock:
                        runtime.error = str(exc)
                    time.sleep(0.5)
                    continue
            t0 = time.monotonic()
            try:
                block = capture.read()
            except CaptureError as exc:
                with runtime.lock:
                    runtime.error = str(exc)
                if capture is not None:
                    capture.close()
                    capture = None
                time.sleep(0.2)
                continue
            sample = classifier.push_block(block)
            leftover = config.block_ms / 1000.0 - (time.monotonic() - t0)
            if leftover > 0:
                time.sleep(leftover)
            with runtime.lock:
                runtime.level = sample.level
                runtime.sample = sample
    finally:
        if capture is not None:
            capture.close()


def _format_line(runtime: Runtime) -> str:
    listening, level, sample, error = runtime.snapshot()
    if error and not listening:
        return f"off     error={error.splitlines()[0]}"
    if not listening:
        return "off     not listening (Off switch)"
    if error:
        return f"wait    {error.splitlines()[0]}"
    if sample is None:
        return "wait    opening monitor…"
    return (
        f"{level:6}  rms={sample.rms:.3f}  slope={sample.slope:+.3f}  "
        f"{sample.db_fs:6.1f} dBFS"
    )


def _text_loop(runtime: Runtime) -> None:
    print(
        f"Mad Lite {__version__}  source={runtime.source_label or '(starting)'}  "
        "q+enter or Ctrl+C to quit; 'off' toggles the kill switch",
        flush=True,
    )

    def stdin_watch() -> None:
        for line in sys.stdin:
            token = line.strip().lower()
            if token in {"q", "quit", "exit"}:
                runtime.request_stop()
                break
            if token in {"off", "on", "toggle"}:
                with runtime.lock:
                    runtime.listening = not runtime.listening

    threading.Thread(target=stdin_watch, name="madlite-stdin", daemon=True).start()
    last = ""
    while not runtime.stopped():
        line = _format_line(runtime)
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(0.15)


def _run_gui(runtime: Runtime, *, pill: bool, tray: bool) -> bool:
    pill_win = None
    tray_ctl = None

    def toggle_off() -> None:
        with runtime.lock:
            runtime.listening = not runtime.listening

    def quit_app() -> None:
        runtime.request_stop()
        if pill_win is not None:
            pill_win.destroy()
        if tray_ctl is not None:
            tray_ctl.stop()

    if pill:
        try:
            from madlite.ui import PillWindow

            pill_win = PillWindow(
                on_off=toggle_off,
                on_quit=quit_app,
            )
        except Exception as exc:
            print(f"pill unavailable ({exc})", file=sys.stderr)
            pill_win = None

    if tray:
        try:
            from madlite.ui import TrayController
        except Exception as exc:
            print(f"tray unavailable ({exc})", file=sys.stderr)
            tray = False
        else:
            def show_pill() -> None:
                if pill_win is None:
                    return
                try:
                    pill_win.root.deiconify()
                    pill_win.root.lift()
                    pill_win.root.attributes("-topmost", True)
                except Exception:
                    pass

            tray_ctl = TrayController(
                on_off=toggle_off,
                on_quit=quit_app,
                on_show_pill=None if pill_win is None else show_pill,
                get_listening=lambda: runtime.snapshot()[0],
                get_level=lambda: runtime.snapshot()[1],
            )
            try:
                tray_ctl.start()
            except Exception as exc:
                print(f"tray failed to start ({exc})", file=sys.stderr)
                tray_ctl = None

    if pill_win is None and tray_ctl is None:
        return False

    def tick() -> None:
        if runtime.stopped():
            quit_app()
            return
        listening, level, _sample, _err = runtime.snapshot()
        if pill_win is not None:
            pill_win.set_state(level, listening)
            pill_win.after(120, tick)
        if tray_ctl is not None:
            tray_ctl.update()

    if pill_win is not None:
        pill_win.after(120, tick)
        try:
            pill_win.mainloop()
        finally:
            runtime.request_stop()
            if tray_ctl is not None:
                tray_ctl.stop()
        return True

    try:
        while not runtime.stopped():
            time.sleep(0.2)
            if tray_ctl is not None:
                tray_ctl.update()
    except KeyboardInterrupt:
        runtime.request_stop()
    finally:
        if tray_ctl is not None:
            tray_ctl.stop()
    return True


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.list_sources:
        return _print_sources()

    config = _config_from_args(args)
    runtime = Runtime()

    def handle_signal(_signum: int, _frame: object | None) -> None:
        runtime.request_stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.demo:
        source = DemoCapture(config).source
        backend = "demo"
    else:
        try:
            source = discover_monitor(args.source, allow_non_monitor=args.allow_mic)
        except CaptureError as exc:
            print(exc, file=sys.stderr)
            return 2
        backend = args.backend

    runtime.source_label = source.label
    worker = threading.Thread(
        target=_audio_loop,
        args=(runtime, config, source, backend),
        name="madlite-audio",
        daemon=True,
    )
    worker.start()

    if not args.text:
        if _run_gui(runtime, pill=not args.no_pill, tray=not args.no_tray):
            runtime.request_stop()
            worker.join(timeout=2.0)
            return 0
        print(
            "GUI unavailable; falling back to --text. Ctrl+C or q+enter to quit.",
            file=sys.stderr,
        )

    try:
        _text_loop(runtime)
    except KeyboardInterrupt:
        runtime.request_stop()
    runtime.request_stop()
    worker.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
