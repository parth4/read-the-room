"""Default-sink monitor capture. Never silently falls back to a microphone."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

import numpy as np

from madlite.heat import HeatConfig


class CaptureError(RuntimeError):
    """No monitor source, or the capture stream failed."""


@dataclass(frozen=True)
class MonitorSource:
    """A sink monitor / loopback — playback you can already hear."""

    pulse_name: str
    label: str
    via: str  # pactl | wpctl | soundcard | cli

    def looks_like_monitor(self) -> bool:
        n = self.pulse_name.lower()
        l = self.label.lower()
        return "monitor" in n or "monitor" in l or "loopback" in l


def _run(cmd: list[str], timeout: float = 3.0) -> str:
    try:
        out = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CaptureError(f"{cmd[0]} failed: {exc}") from exc
    return out.stdout


def parse_pactl_short_sources(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].strip():
            names.append(parts[1].strip())
    return names


def parse_pactl_sink_monitor(text: str, sink_name: str) -> str | None:
    """Return Monitor Source for the named sink from `pactl list sinks`."""
    blocks = text.split("\nSink ")
    for block in blocks:
        name = ""
        monitor = ""
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("Name:"):
                name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Monitor Source:"):
                monitor = stripped.split(":", 1)[1].strip()
        if name == sink_name and monitor:
            return monitor
    return None


def _pactl_default_monitor() -> MonitorSource:
    sink = _run(["pactl", "get-default-sink"]).strip()
    if not sink:
        raise CaptureError("pactl reported an empty default sink")
    try:
        listing = _run(["pactl", "list", "sinks"])
        monitor = parse_pactl_sink_monitor(listing, sink)
    except CaptureError:
        monitor = None
    if not monitor:
        monitor = f"{sink}.monitor"
    try:
        sources = parse_pactl_short_sources(_run(["pactl", "list", "short", "sources"]))
    except CaptureError:
        sources = []
    if sources and monitor not in sources:
        # PipeWire sometimes omits the .monitor suffix in short listings.
        alt = next((s for s in sources if s == sink or s.startswith(f"{sink}.")), None)
        if alt:
            monitor = alt
        elif not any("monitor" in s.lower() for s in sources):
            raise CaptureError(
                f"default sink {sink!r} has no monitor source in `pactl list short sources`"
            )
    return MonitorSource(pulse_name=monitor, label=f"monitor of {sink}", via="pactl")


def _soundcard_default_monitor() -> MonitorSource:
    try:
        import soundcard as sc

        speaker = sc.default_speaker()
    except Exception as exc:  # import can assert if Pulse/PipeWire is down
        raise CaptureError(
            f"soundcard loopback unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    pulse_id = getattr(speaker, "id", None) or speaker.name
    candidate_ids = [f"{pulse_id}.monitor", pulse_id, speaker.name]
    last_err: Exception | None = None
    for ident in candidate_ids:
        try:
            mic = sc.get_microphone(ident, include_loopback=True)
        except Exception as exc:
            last_err = exc
            continue
        if getattr(mic, "isloopback", False):
            return MonitorSource(
                pulse_name=getattr(mic, "id", ident),
                label=f"loopback of {speaker.name}",
                via="soundcard",
            )
    for mic in sc.all_microphones(include_loopback=True):
        if not getattr(mic, "isloopback", False):
            continue
        name = mic.name
        if speaker.name in name or pulse_id in getattr(mic, "id", ""):
            return MonitorSource(
                pulse_name=getattr(mic, "id", name),
                label=name,
                via="soundcard",
            )
    raise CaptureError(
        f"soundcard could not find a loopback for {speaker.name!r}: {last_err}"
    )


def _refuse_mic(source: MonitorSource, *, allow_non_monitor: bool) -> MonitorSource:
    if source.looks_like_monitor() or allow_non_monitor:
        return source
    raise CaptureError(
        f"{source.pulse_name!r} does not look like a sink monitor. "
        "Mad Lite will not open a microphone unless you pass --allow-mic."
    )


def discover_monitor(
    explicit: str | None = None,
    *,
    allow_non_monitor: bool = False,
) -> MonitorSource:
    """Resolve the capture source. Default: monitor of the current default sink."""
    if explicit:
        return _refuse_mic(
            MonitorSource(pulse_name=explicit, label=explicit, via="cli"),
            allow_non_monitor=allow_non_monitor,
        )
    errors: list[str] = []
    for finder in (_pactl_default_monitor, _soundcard_default_monitor):
        try:
            return _refuse_mic(finder(), allow_non_monitor=allow_non_monitor)
        except Exception as exc:
            errors.append(str(exc))
    hint = (
        "Could not find a monitor source for the default sink.\n"
        "  • Make headphones (or speakers) the default output: pactl get-default-sink\n"
        "  • List monitors: madlite --list-sources\n"
        "  • Then: madlite --source <name.monitor>\n"
        "Mad Lite does not fall back to the microphone."
    )
    raise CaptureError(hint + "\n\nTried:\n  - " + "\n  - ".join(errors))


def list_monitor_sources() -> list[MonitorSource]:
    """Monitors / loopbacks only — never the raw mic list as the default view."""
    found: dict[str, MonitorSource] = {}
    if shutil.which("pactl"):
        try:
            sink = _run(["pactl", "get-default-sink"]).strip()
        except CaptureError:
            sink = ""
        try:
            for name in parse_pactl_short_sources(_run(["pactl", "list", "short", "sources"])):
                if "monitor" not in name.lower():
                    continue
                label = name
                if sink and (name == f"{sink}.monitor" or name.startswith(sink)):
                    label = f"{name}  (default sink)"
                found[name] = MonitorSource(pulse_name=name, label=label, via="pactl")
        except CaptureError:
            pass
    try:
        import soundcard as sc

        for mic in sc.all_microphones(include_loopback=True):
            if not getattr(mic, "isloopback", False):
                continue
            ident = getattr(mic, "id", mic.name)
            found.setdefault(
                ident,
                MonitorSource(pulse_name=ident, label=mic.name, via="soundcard"),
            )
    except Exception:
        pass
    return list(found.values())


class _PulsePipeCapture:
    def __init__(
        self,
        source: MonitorSource,
        config: HeatConfig,
        argv: list[str],
    ) -> None:
        self.source = source
        self._frames = config.block_frames
        self._proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
        )
        if self._proc.stdout is None:
            self.close()
            raise CaptureError("capture process has no stdout pipe")

    def read(self) -> np.ndarray:
        assert self._proc.stdout is not None
        need = self._frames * 4
        buf = self._proc.stdout.read(need)
        if len(buf) < need:
            err = ""
            if self._proc.stderr is not None:
                err = self._proc.stderr.read().decode("utf-8", "replace")[:400]
            raise CaptureError(
                f"capture stream ended after {len(buf)} bytes. {err}".strip()
            )
        return np.frombuffer(buf, dtype=np.float32).copy()

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                self._proc.kill()


class SoundcardCapture:
    def __init__(self, source: MonitorSource, config: HeatConfig) -> None:
        import soundcard as sc

        self.source = source
        self._frames = config.block_frames
        self._mic = sc.get_microphone(source.pulse_name, include_loopback=True)
        if not getattr(self._mic, "isloopback", False) and "monitor" not in source.pulse_name.lower():
            raise CaptureError(
                f"soundcard source {source.pulse_name!r} is not a loopback/monitor"
            )
        self._recorder = self._mic.recorder(
            samplerate=config.sample_rate,
            channels=1,
            blocksize=config.block_frames,
        )
        self._stream = self._recorder.__enter__()

    def read(self) -> np.ndarray:
        data = np.asarray(self._stream.record(numframes=self._frames), dtype=np.float32)
        return data

    def close(self) -> None:
        try:
            self._recorder.__exit__(None, None, None)
        except Exception:
            pass


class DemoCapture:
    """Synthetic energy pattern. No device, no disk."""

    def __init__(self, config: HeatConfig) -> None:
        self.source = MonitorSource(
            pulse_name="demo",
            label="synthetic energy (no audio device)",
            via="demo",
        )
        self._config = config
        self._t = 0.0

    def read(self) -> np.ndarray:
        n = self._config.block_frames
        sr = self._config.sample_rate
        amp = _demo_amplitude(self._t)
        t = self._t + np.arange(n, dtype=np.float64) / sr
        # Sine RMS = amp / sqrt(2) — predictable heat, no device.
        block = (amp * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
        self._t += n / sr
        return block

    def close(self) -> None:
        return


def _demo_amplitude(t: float) -> float:
    """~10s loop: quiet → climb → hot → fade. Peak amplitude of a sine."""
    cycle = 10.0
    x = t % cycle
    if x < 2.0:
        return 0.006
    if x < 5.5:
        return 0.006 + (x - 2.0) / 3.5 * 0.10
    if x < 8.0:
        return 0.22
    return 0.22 * max(0.0, 1.0 - (x - 8.0) / 2.0)


def open_capture(
    source: MonitorSource,
    config: HeatConfig,
    backend: str = "auto",
) -> SoundcardCapture | _PulsePipeCapture | DemoCapture:
    if backend == "demo" or source.via == "demo":
        return DemoCapture(config)

    order: list[str]
    if backend == "auto":
        order = ["soundcard", "parec", "pw-record"]
    else:
        order = [backend]

    errors: list[str] = []
    for name in order:
        try:
            if name == "soundcard":
                return SoundcardCapture(source, config)
            if name == "parec":
                if not shutil.which("parec"):
                    raise CaptureError("parec not on PATH")
                return _PulsePipeCapture(
                    source,
                    config,
                    [
                        "parec",
                        f"--device={source.pulse_name}",
                        "--format=float32le",
                        f"--rate={config.sample_rate}",
                        "--channels=1",
                    ],
                )
            if name == "pw-record":
                if not shutil.which("pw-record"):
                    raise CaptureError("pw-record not on PATH")
                return _PulsePipeCapture(
                    source,
                    config,
                    [
                        "pw-record",
                        f"--target={source.pulse_name}",
                        "--format=f32",
                        f"--rate={config.sample_rate}",
                        "--channels=1",
                        "-",
                    ],
                )
            raise CaptureError(f"unknown backend {name!r}")
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise CaptureError("no capture backend worked:\n  - " + "\n  - ".join(errors))
