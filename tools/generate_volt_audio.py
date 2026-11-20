"""Generate original, softly limited mono coil sounds for Volt.

Only sine/FM oscillators and seeded, filtered noise are used. No recordings,
sample libraries or third-party musical material are part of these assets.
"""

import argparse
from array import array
import base64
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/assets/audio"
QA = ROOT / ".cache/volt-refinement/audio"
RATE = 22050
SPECS = {
    "volt_pulse": {"seconds": .43, "seed": 8201, "peak": .72, "rms": .18},
    "volt_charge": {"seconds": .56, "seed": 8202, "peak": .66, "rms": .17},
    "volt_storm": {"seconds": .90, "seed": 8203, "peak": .80, "rms": .21},
    "volt_shutdown": {"seconds": .90, "seed": 8204, "peak": .60, "rms": .15},
}


def smooth(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def window(t, start, end, attack=.012, release=.08):
    if t <= start or t >= end:
        return 0.0
    return smooth((t - start) / attack) * smooth((end - t) / release)


class Oscillator:
    def __init__(self):
        self.phase = 0.0

    def step(self, frequency, phase_offset=0):
        self.phase = (self.phase + math.tau * frequency / RATE) % math.tau
        return math.sin(self.phase + phase_offset)


class LowPass:
    def __init__(self):
        self.value = 0.0

    def step(self, value, cutoff):
        alpha = 1 - math.exp(-math.tau * cutoff / RATE)
        self.value += alpha * (value - self.value)
        return self.value


def synthesize(name, spec):
    rng = random.Random(spec["seed"])
    carriers = [Oscillator() for _ in range(5)]
    hiss_filter, body_filter = LowPass(), LowPass()
    count = round(spec["seconds"] * RATE)
    samples = []
    for index in range(count):
        t = index / RATE
        u = t / spec["seconds"]
        white = rng.uniform(-1, 1)
        hiss = hiss_filter.step(white, 2300 if name != "volt_shutdown" else 1100)
        rumble = body_filter.step(white, 220)
        if name == "volt_pulse":
            envelope = window(t, 0, spec["seconds"], .009, .14) * math.exp(-3.3 * u)
            mod = carriers[0].step(79 + 38 * (1 - u))
            electric = carriers[1].step(290 + 920 * math.exp(-8 * u), .95 * mod)
            overtone = carriers[2].step(1770 - 1150 * u)
            bass = carriers[3].step(125 - 35 * u)
            sparkle = window(t, .075, .22, .008, .07)
            signal = envelope * (.62 * electric + .22 * bass + .24 * hiss)
            signal += .14 * overtone * sparkle
        elif name == "volt_charge":
            envelope = window(t, 0, spec["seconds"], .045, .075)
            rise = smooth(u)
            fundamental = carriers[0].step(112 + 315 * rise)
            harmonic = carriers[1].step(224 + 630 * rise, .22 * fundamental)
            shiver = .55 + .45 * carriers[2].step(7 + 25 * u)
            contact = carriers[3].step(690 + 810 * rise, .38 * harmonic)
            signal = envelope * (.48 * fundamental + .20 * harmonic
                                  + .16 * contact * shiver + .22 * hiss * shiver)
        elif name == "volt_storm":
            windup = window(t, 0, .39, .045, .065)
            load = carriers[0].step(135 + 440 * smooth(t / .35))
            coil = carriers[1].step(570 + 620 * smooth(t / .35), .3 * load)
            signal = windup * (.22 * load + .15 * coil + .12 * hiss)
            for burst_at, strength in ((.30, 1.0), (.42, .64), (.57, .43)):
                delta = max(0.0, t - burst_at)
                bolt = window(t, burst_at, min(.89, burst_at + .29), .006, .12)
                bolt *= math.exp(-8 * delta)
                flicker = .7 + .3 * math.sin(91 * delta)
                signal += strength * bolt * (.58 * hiss * flicker + .33 * rumble)
            tail = window(t, .30, .90, .012, .22) * math.exp(-4 * max(0, t - .3))
            impact = carriers[2].step(66 + 115 * math.exp(-9 * max(0, t - .3)))
            resonance = carriers[3].step(410 - 190 * u)
            signal += tail * (.37 * impact + .14 * resonance)
        else:
            envelope = window(t, 0, spec["seconds"], .018, .19)
            fall = (1 - u) ** 1.7
            whine = carriers[0].step(72 + 540 * fall)
            overtone = carriers[1].step(144 + 1080 * fall, .24 * whine)
            flutter = .75 + .25 * carriers[2].step(13 + 16 * fall)
            dying = (1 - smooth(u)) ** .65
            sputter = window(t, .12, .67, .025, .20) * (.5 + .5 * math.sin(78 * t)) ** 2
            signal = envelope * dying * (.48 * whine + .14 * overtone) * flutter
            signal += envelope * (.13 * hiss * sputter + .17 * rumble * dying)
        samples.append(math.tanh(1.35 * signal) / 1.35)

    # A gentle DC blocker followed by exact, zero-ended DC correction. The
    # final 8 ms cosine-like fades also protect concatenation at arbitrary FPS.
    blocked, last_in, last_out = [], 0.0, 0.0
    pole = math.exp(-math.tau * 22 / RATE)
    edge = []
    for index, sample in enumerate(samples):
        filtered = sample - last_in + pole * last_out
        last_in, last_out = sample, filtered
        fade = smooth(index / (RATE * .008)) * smooth((count - 1 - index) / (RATE * .008))
        edge.append(fade)
        blocked.append(filtered * fade)
    correction = sum(blocked) / sum(edge)
    blocked = [sample - correction * fade for sample, fade in zip(blocked, edge)]
    peak = max(abs(sample) for sample in blocked)
    rms = math.sqrt(sum(sample * sample for sample in blocked) / count)
    scale = min(spec["peak"] / max(peak, 1e-12), spec["rms"] / max(rms, 1e-12))
    return [round(min(.89, max(-.89, sample * scale)) * 32767) for sample in blocked]


def write_wav(path, samples, *, rate=RATE, width=2):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(width)
        stream.setframerate(rate)
        if width == 2:
            stream.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        else:
            stream.writeframes(bytes(samples))


def inspect(path):
    with wave.open(str(path), "rb") as stream:
        assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) == (1, 2, RATE, "NONE")
        count = stream.getnframes()
        raw = stream.readframes(count)
    integers = array("h")
    integers.frombytes(raw)
    if sys.byteorder != "little":
        integers.byteswap()
    normalized = [value / 32768 for value in integers]
    peak = max(abs(value) for value in normalized)
    rms = math.sqrt(sum(value * value for value in normalized) / count)
    mean = sum(normalized) / count
    edge_count = round(RATE * .001)
    steps = [abs(normalized[i + 1] - normalized[i]) for i in range(count - 1)]
    end_step = max(steps[:edge_count] + steps[-edge_count:])
    assert peak < .90 and .025 < rms < .24
    assert abs(mean) < .0001 and integers[0] == integers[-1] == 0
    assert end_step < .04, (path.name, end_step)
    return {
        "file": str(path.relative_to(ROOT)), "format": "PCM signed 16-bit little-endian",
        "channels": 1, "sample_rate": RATE, "frames": count,
        "seconds": round(count / RATE, 6), "peak": round(peak, 6),
        "rms": round(rms, 6), "dc_mean": round(mean, 8),
        "edge_step_peak_1ms": round(end_step, 6),
        "first_sample": integers[0], "last_sample": integers[-1],
        "clipped_samples": sum(abs(value) >= round(.90 * 32768) for value in integers),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }, integers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--preview-base64", action="store_true", help="Emit only a small 8 kHz audition data URL as JSON")
    args = parser.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    checks, previews = [], []
    for name, spec in SPECS.items():
        path = ASSETS / f"{name}.wav"
        if not args.verify_only:
            write_wav(path, synthesize(name, spec))
        check, pcm = inspect(path)
        assert abs(check["seconds"] - spec["seconds"]) <= 1 / RATE
        checks.append(check)
        # Low-bandwidth audition only; the production assets above stay 22.05 kHz/16-bit.
        preview_rate = 8000
        size = round(len(pcm) * preview_rate / RATE)
        previews += [min(255, max(0, 128 + round(pcm[min(len(pcm) - 1, round(i * RATE / preview_rate))] / 256))) for i in range(size)]
        previews += [128] * round(.16 * preview_rate)
    report = {
        "original_procedural_synthesis": True, "external_samples_used": False,
        "source": "tools/generate_volt_audio.py", "deterministic_seeds": True,
        "physical_android_audio_tested": False, "checks_passed": True, "sounds": checks,
    }
    (QA / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    preview_path = QA / "preview.wav"
    write_wav(preview_path, previews, rate=8000, width=1)
    if args.preview_base64:
        print(json.dumps({"audio_url": "data:audio/wav;base64," + base64.b64encode(preview_path.read_bytes()).decode()}))
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
