"""Original short character chirps and mechanical dance sounds, no samples."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random

from generate_volt_audio import Oscillator, LowPass, inspect, smooth, window, write_wav, RATE

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/assets/audio"
QA = ROOT / ".cache/robot-audio-v35"
SPECS = {
    "robot_reply_light": (.22, 9301),
    "robot_reply_heavy": (.28, 9302),
    "robot_reply_bio": (.27, 9303),
    "robot_reply_air": (.25, 9304),
    "robot_reply_spectral": (.29, 9305),
    "robot_reply_beast": (.26, 9306),
    "robot_servo": (.17, 9307),
    "robot_step_heavy": (.19, 9308),
    "robot_wheel": (.23, 9309),
    "robot_hover": (.22, 9310),
    "robot_dance_tick": (.10, 9311),
    "robot_dance_bass": (.18, 9312),
    "robot_dance_chime": (.23, 9313),
    "robot_surprise": (.22, 9314),
    "robot_grump": (.26, 9315),
    "robot_powerdown": (.43, 9316),
    "robot_charge": (.34, 9317),
    "robot_reply_electric": (.24, 9318),
}


def synthesize(name, seconds, seed):
    rng = random.Random(seed)
    oscillators = [Oscillator() for _ in range(5)]
    high, low = LowPass(), LowPass()
    count = round(RATE * seconds)
    data = []
    for i in range(count):
        t, u = i / RATE, i / count
        noise = rng.uniform(-1, 1)
        hiss, body = high.step(noise, 2200), low.step(noise, 190)
        envelope = window(t, 0, seconds, .008, min(.08, seconds * .35))
        if name == "robot_reply_light":
            note = 720 if u < .42 else 1020
            voice = oscillators[0].step(note + 35 * math.sin(u * math.pi), .3 * oscillators[1].step(22))
            signal = .58 * voice + .12 * oscillators[2].step(note * 2.01) + .10 * hiss
        elif name == "robot_reply_electric":
            pitch = 590 + 610 * smooth(u if u < .5 else 1-u)
            signal = .45 * oscillators[0].step(pitch, .38 * oscillators[1].step(57))
            signal += .16 * oscillators[2].step(pitch*2.01) + .10 * hiss
        elif name == "robot_reply_heavy":
            note = 123 + 85 * math.sin(math.pi * u)
            signal = .58 * oscillators[0].step(note, .45 * oscillators[1].step(47))
            signal += .20 * oscillators[2].step(note * 2.03) + .18 * body
        elif name == "robot_reply_bio":
            signal = .48 * oscillators[0].step(530 + 110 * u)
            signal += .23 * oscillators[1].step(795 + 165 * u) + .12 * oscillators[2].step(1060 + 220 * u)
            signal *= .7 + .3 * math.sin(math.pi * u)
        elif name == "robot_reply_air":
            signal = .28 * oscillators[0].step(630 + 380 * math.sin(u * math.pi))
            signal += .28 * hiss * (.5 + .5 * math.sin(u * math.pi)) + .17 * oscillators[1].step(315 + 90 * u)
        elif name == "robot_reply_spectral":
            signal = .42 * oscillators[0].step(410 + 210 * math.sin(u * math.pi), .7 * oscillators[1].step(83))
            signal += .22 * oscillators[2].step(823 - 160 * u) + .10 * hiss
        elif name == "robot_reply_beast":
            signal = .48 * oscillators[0].step(180 + 170 * (1-u), .85 * oscillators[1].step(91))
            signal += .23 * body + .12 * hiss * (.5 + .5 * math.sin(u * 31))
        elif name == "robot_servo":
            signal = .42 * oscillators[0].step(240 + 390 * math.sin(u * math.pi))
            signal += .18 * hiss + .12 * oscillators[1].step(1210 - 500 * u)
        elif name == "robot_step_heavy":
            signal = .52 * oscillators[0].step(65 + 110 * math.exp(-10*u)) + .27 * body + .10 * hiss
            signal *= math.exp(-3.5*u)
        elif name == "robot_wheel":
            ratchet = (.55 + .45 * math.sin(u * 61)) ** 2
            signal = .40 * oscillators[0].step(150 + 80 * math.sin(math.pi*u)) + .25 * hiss * ratchet
        elif name == "robot_hover":
            signal = .30 * oscillators[0].step(170 + 30 * math.sin(u*math.pi)) + .28 * hiss
            signal += .12 * oscillators[1].step(350 + 80*u)
        elif name == "robot_dance_tick":
            signal = (.42 * hiss + .28 * oscillators[0].step(1660 - 900*u)) * math.exp(-8*u)
        elif name == "robot_dance_bass":
            signal = (.63 * oscillators[0].step(67 + 100 * math.exp(-10*u)) + .10 * body) * math.exp(-3*u)
        elif name == "robot_dance_chime":
            signal = (.46 * oscillators[0].step(659.25) + .24 * oscillators[1].step(987.77)
                      + .10 * oscillators[2].step(1318.5)) * math.exp(-2*u)
        elif name == "robot_surprise":
            signal = .47 * oscillators[0].step(400 + 740*smooth(u)) + .16 * oscillators[1].step(800 + 1480*smooth(u))
        elif name == "robot_grump":
            signal = .46 * oscillators[0].step(420 - 240*smooth(u), .6 * oscillators[1].step(38)) + .20 * body
        elif name == "robot_powerdown":
            signal = (.48 * oscillators[0].step(75 + 390*(1-u)**2) + .14 * hiss) * (1-u)
        else:
            signal = .38 * oscillators[0].step(160 + 480*smooth(u), .3 * oscillators[1].step(32)) + .20 * hiss
        data.append(math.tanh(1.35 * signal) * envelope)
    # Original synthesis only. Fade and remove DC before peak/RMS limiting.
    fade = [smooth(i/(RATE*.007))*smooth((count-1-i)/(RATE*.007)) for i in range(count)]
    correction = sum(value*weight for value,weight in zip(data,fade)) / sum(fade)
    data = [(value-correction)*weight for value,weight in zip(data,fade)]
    peak = max(map(abs,data))
    rms = math.sqrt(sum(value*value for value in data)/count)
    gain = min(.70/max(peak,1e-12), .15/max(rms,1e-12))
    return [round(max(-.88,min(.88,value*gain))*32767) for value in data]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    ASSETS.mkdir(parents=True,exist_ok=True)
    QA.mkdir(parents=True,exist_ok=True)
    result = []
    for name,(seconds,seed) in SPECS.items():
        target = ASSETS / (name+".wav")
        expected = synthesize(name,seconds,seed)
        if not args.verify_only:
            write_wav(target,expected)
        metrics,actual = inspect(target)
        assert list(actual) == expected, name
        assert abs(metrics["seconds"]-seconds) <= 1/RATE
        result.append(metrics)
    report={"original_procedural_synthesis":True,"external_samples":False,"sounds":result,
            "total_bytes":sum((ASSETS/(name+".wav")).stat().st_size for name in SPECS),
            "physical_audio_tested":False}
    (QA/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"sounds":len(result),"total_bytes":report["total_bytes"],"checks":"passed"}))


if __name__=="__main__":
    main()
