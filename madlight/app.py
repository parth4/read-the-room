"""CLI and runtime: capture → heat → LED / tray / text."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from dataclasses import dataclass, field, replace

from madlight import __version__
from madlight.audio import (
    CaptureError,
    DemoCapture,
    MonitorSource,
    discover_monitor,
    list_monitor_sources,
    open_capture,
)
from madlight.heat import (
    HeatClassifier,
    HeatConfig,
    HeatLevel,
    HeatSample,
    MeterSmoother,
    activity_lanes,
    block_rms,
    is_idle,
)
from madlight.prefs import (
    apply_prefs,
    append_feedback,
    load_prefs,
    note_feedback,
    save_prefs,
    set_sensitivity,
)

# Keep in sync with madlight.ui.WAVE_BARS (history of capture-block RMS).
_WAVE_BARS = 28


@dataclass
class Runtime:
    listening: bool = True
    stop: bool = False
    level: HeatLevel = HeatLevel.CALM
    sample: HeatSample | None = None
    idle: bool = True
    wave: list[float] = field(default_factory=lambda: [0.0] * _WAVE_BARS)
    lanes: tuple[float, float, float] = (0.0, 0.0, 0.0)
    source_label: str = ""
    error: str | None = None
    config: HeatConfig = field(default_factory=HeatConfig)
    meter: MeterSmoother = field(default_factory=lambda: MeterSmoother(bars=_WAVE_BARS))
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(
        self,
    ) -> tuple[
        bool,
        HeatLevel,
        HeatSample | None,
        str | None,
        bool,
        tuple[float, ...],
        tuple[float, float, float],
    ]:
        with self.lock:
            return (
                self.listening,
                self.level,
                self.sample,
                self.error,
                self.idle,
                tuple(self.wave),
                self.lanes,
            )

    def set_listening(self, value: bool) -> None:
        with self.lock:
            self.listening = value
            if not value:
                self.level = HeatLevel.CALM
                self.sample = None
                self.idle = True
                self.meter.reset()
                self.wave = [0.0] * len(self.wave)
                self.lanes = (0.0, 0.0, 0.0)

    def request_stop(self) -> None:
        with self.lock:
            self.stop = True
            self.listening = False
            self.idle = True

    def stopped(self) -> bool:
        with self.lock:
            return self.stop

    def apply_config(self, cfg: HeatConfig) -> None:
        with self.lock:
            self.config = cfg
            self.meter.stride = max(1, cfg.meter_stride)
            self.meter.lane_alpha = cfg.lane_ema


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="madlight",
        description=(
            "Mad Light — Meeting Atmosphere Dial. Local RMS/slope heat LED "
            "(recording-indicator dot). Captures the default sink monitor "
            "(headphones or speakers), never the cloud."
        ),
        epilog="Offline critic: madlight calibrate --manifest FILE  (see CALIBRATE.md)",
    )
    p.add_argument("--version", action="version", version=f"madlight {__version__}")
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
    p.add_argument("--no-dot", action="store_true", help="do not open the Tk LED")
    p.add_argument("--no-pill", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--no-tray", action="store_true", help="do not start the tray icon")
    p.add_argument("--rising-rms", type=float, default=None)
    p.add_argument("--hot-rms", type=float, default=None)
    p.add_argument("--rising-slope", type=float, default=None)
    return p


def _config_from_args(args: argparse.Namespace, base: HeatConfig | None = None) -> HeatConfig:
    cfg = base or HeatConfig()
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
                classifier.config = runtime.config
                cfg = runtime.config
            if not listening:
                if capture is not None:
                    capture.close()
                    capture = None
                    classifier.reset()
                with runtime.lock:
                    runtime.idle = True
                    runtime.meter.reset()
                    runtime.wave = [0.0] * len(runtime.wave)
                    runtime.lanes = (0.0, 0.0, 0.0)
                    runtime.sample = None
                    runtime.level = HeatLevel.CALM
                time.sleep(0.05)
                continue
            if capture is None:
                try:
                    capture = open_capture(source, cfg, backend=backend)
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
            instant = block_rms(block)
            lanes = activity_lanes(block, cfg.sample_rate)
            leftover = cfg.block_ms / 1000.0 - (time.monotonic() - t0)
            if leftover > 0:
                time.sleep(leftover)
            with runtime.lock:
                wave, smooth_lanes = runtime.meter.push(instant, lanes)
                runtime.level = sample.level
                runtime.sample = sample
                runtime.idle = is_idle(sample.rms, cfg.silence_rms)
                runtime.wave = wave
                runtime.lanes = smooth_lanes
    finally:
        if capture is not None:
            capture.close()


def _format_line(runtime: Runtime) -> str:
    listening, level, sample, error, idle, _wave, _lanes = runtime.snapshot()
    if error and not listening:
        return f"paused  error={error.splitlines()[0]}"
    if not listening:
        return "paused  not listening (pause / Off switch)"
    if error:
        return f"wait    {error.splitlines()[0]}"
    if sample is None:
        return "wait    opening monitor…"
    tag = "idle" if idle else f"{level:6}"
    return (
        f"{tag:6}  rms={sample.rms:.3f}  slope={sample.slope:+.3f}  "
        f"{sample.db_fs:6.1f} dBFS"
    )


def _text_loop(runtime: Runtime) -> None:
    print(
        f"Mad Light {__version__}  source={runtime.source_label or '(starting)'}  "
        "q+enter or Ctrl+C to quit; 'off'/'pause' toggles the kill switch",
        flush=True,
    )

    def stdin_watch() -> None:
        for line in sys.stdin:
            token = line.strip().lower()
            if token in {"q", "quit", "exit"}:
                runtime.request_stop()
                break
            if token in {"off", "on", "toggle", "pause", "resume"}:
                runtime.set_listening(not runtime.listening)

    threading.Thread(target=stdin_watch, name="madlight-stdin", daemon=True).start()
    last = ""
    while not runtime.stopped():
        line = _format_line(runtime)
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(0.15)


def _run_gui(runtime: Runtime, *, dot: bool, tray: bool) -> bool:
    dot_win = None
    tray_ctl = None

    def toggle_off() -> None:
        runtime.set_listening(not runtime.listening)

    def quit_app() -> None:
        runtime.request_stop()
        if dot_win is not None:
            dot_win.destroy()
        if tray_ctl is not None:
            tray_ctl.stop()

    def on_feedback(label: str) -> None:
        listening, level, sample, _err, idle, _wave, _lanes = runtime.snapshot()
        with runtime.lock:
            cfg = runtime.config
        append_feedback(
            label,
            sample=sample,
            listening=listening,
            idle=idle,
            level=level,
            extra={"rising_rms": cfg.rising_rms, "hot_rms": cfg.hot_rms},
        )
        prefs = load_prefs()
        prefs, nudged = note_feedback(prefs, label, level, idle=idle)
        save_prefs(prefs)
        if nudged:
            runtime.apply_config(apply_prefs(HeatConfig(), prefs))

    def on_sensitivity(name: str) -> None:
        prefs = set_sensitivity(load_prefs(), name)
        save_prefs(prefs)
        runtime.apply_config(apply_prefs(HeatConfig(), prefs))

    if dot:
        try:
            from madlight.ui import DotWindow

            dot_win = DotWindow(
                on_off=toggle_off,
                on_quit=quit_app,
                on_feedback=on_feedback,
                on_sensitivity=on_sensitivity,
                get_sensitivity=lambda: load_prefs().sensitivity_name(),
            )
        except Exception as exc:
            print(f"LED unavailable ({exc})", file=sys.stderr)
            dot_win = None

    if tray:
        try:
            from madlight.ui import TrayController
        except Exception as exc:
            print(f"tray unavailable ({exc})", file=sys.stderr)
            tray = False
        else:
            def show_dot() -> None:
                if dot_win is None:
                    return
                try:
                    dot_win.root.deiconify()
                    dot_win.root.lift()
                    dot_win.root.attributes("-topmost", True)
                except Exception:
                    pass

            tray_ctl = TrayController(
                on_off=toggle_off,
                on_quit=quit_app,
                on_show_dot=None if dot_win is None else show_dot,
                get_listening=lambda: runtime.snapshot()[0],
                get_level=lambda: runtime.snapshot()[1],
                get_idle=lambda: runtime.snapshot()[4],
            )
            try:
                tray_ctl.start()
            except Exception as exc:
                print(f"tray failed to start ({exc})", file=sys.stderr)
                tray_ctl = None

    if dot_win is None and tray_ctl is None:
        return False

    def tick() -> None:
        if runtime.stopped():
            quit_app()
            return
        listening, level, _sample, _err, idle, wave, lanes = runtime.snapshot()
        if dot_win is not None:
            dot_win.set_state(level, listening, idle=idle, wave=wave, lanes=lanes)
            dot_win.after(50, tick)
        if tray_ctl is not None:
            tray_ctl.update()

    if dot_win is not None:
        dot_win.after(120, tick)
        try:
            dot_win.mainloop()
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
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "calibrate":
        from madlight.calibrate import main as calibrate_main

        return calibrate_main(argv[1:])

    args = _build_parser().parse_args(argv)
    if args.list_sources:
        return _print_sources()

    prefs = load_prefs()
    config = _config_from_args(args, base=apply_prefs(HeatConfig(), prefs))
    runtime = Runtime()
    runtime.apply_config(config)

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
        name="madlight-audio",
        daemon=True,
    )
    worker.start()

    show_dot = not (args.no_dot or args.no_pill)
    if not args.text:
        if _run_gui(runtime, dot=show_dot, tray=not args.no_tray):
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
