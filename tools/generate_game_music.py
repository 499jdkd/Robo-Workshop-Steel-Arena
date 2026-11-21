"""Small original loop arrangements; existing WAV assets remain unchanged."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
RATE = 22050


def tone(data, at, duration, midi, gain, bright=False):
    frequency = 440 * 2 ** ((midi-69)/12)
    start = round(at*RATE)
    for j in range(min(round(duration*RATE), len(data)-start)):
        t = j/RATE
        env = min(1, t/.018) * min(1, (duration-t)/.09)
        env *= math.exp(-t*(2.8 if bright else 1.2))
        phase = math.tau*frequency*t
        signal = math.sin(phase)+.18*math.sin(phase*2)+.06*math.sin(phase*3)
        data[start+j] += gain*env*signal


def main():
    out=ROOT/'.cache/volt-motion-v36/music';out.mkdir(parents=True,exist_ok=True)
    assets=ROOT/'src/assets/audio'
    specs={'music_workshop':(8.0,.5),'music_arena':(8.0,.5),'music_victory':(4.0,.25)}
    report={}
    for name,(duration,beat) in specs.items():
        samples=[0.0]*round(duration*RATE)
        if name=='music_victory':
            # Keep the existing recognizable victory motif as the opening voice.
            with wave.open(str(assets/'victory.wav'),'rb') as original:
                assert original.getnchannels()==1 and original.getframerate()==RATE
                old=array('h',original.readframes(original.getnframes()))
            for i,value in enumerate(old):samples[i] += value/32768*.45
            for i,note in enumerate([64,67,72,76,74,79,76,84]):
                tone(samples,.5+i*.3,.65,note,.09,True)
            for note in [48,55,60,64,67]:tone(samples,2.3,1.55,note,.043)
        else:
            chords=[[48,55,60,64],[45,52,57,60],[41,48,53,57],[43,50,55,59]]
            for bar,chord in enumerate(chords):
                for note in chord:tone(samples,bar*2,1.8,note,.024)
                pattern=[0,2,1,3] if name=='music_workshop' else [0,1,2,1]
                for step,index in enumerate(pattern):
                    tone(samples,bar*2+step*beat,.38,chord[index]+12,.038,True)
                    if name=='music_arena':tone(samples,bar*2+step*beat,.21,chord[0]-12,.055)
        # A short silent/zero-slope boundary prevents a click at the loop seam.
        for i in range(len(samples)):
            samples[i]*=min(1,i/(RATE*.02),(len(samples)-1-i)/(RATE*.04))
        peak=max(map(abs,samples));gain=.65/max(peak,1e-8)
        pcm=array('h',(round(s*gain*32767) for s in samples))
        path=out/(name+'.wav')
        with wave.open(str(path),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm.tobytes())
        target=assets/(name+'.ogg')
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(path),'-c:a','libvorbis','-q:a','2',str(target)],capture_output=True,check=True)
        report[name]={'seconds':duration,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'peak':round(peak*gain,4),'original_arrangement':True}
    (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
