"""Original seeded mechanical sound design, no recordings or sampled libraries."""
from array import array
import hashlib,json,math,random,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RATE=22050
SPECS={'titan_ram':.48,'titan_hydraulic':.46,'titan_step':.32,'titan_pressure':1.5,
       'titan_bastion':.85,'titan_quake':1.45,'titan_rumble':.88,'titan_shutdown':1.6}
def synth(name,seconds,seed):
    rng=random.Random(seed);filtered=0.;phase=0.;samples=[]
    for i in range(round(seconds*RATE)):
        t=i/RATE;u=t/seconds;noise=rng.uniform(-1,1)
        filtered+=.045*(noise-filtered)
        freq=65+(110*u if name=='titan_pressure' else 48*(1-u))
        phase+=math.tau*freq/RATE
        bass=math.sin(phase)+.25*math.sin(phase*2.03)
        if name in {'titan_ram','titan_step','titan_quake'}:
            env=(1-math.exp(-t*200))*math.exp(-u*(6 if name!='titan_quake' else 4))
            signal=env*(.5*bass+.35*noise*math.exp(-u*18)+.6*filtered)
            if name=='titan_quake':signal+=.25*math.sin(phase*.48)*math.sin(math.pi*u)**2
        elif name=='titan_pressure':
            env=math.sin(math.pi*u)**.65
            signal=env*(.24*bass+.5*filtered+.09*noise*(.4+.6*u))
            signal+=.07*env*math.sin(t*math.tau*(440+140*u))
        elif name=='titan_bastion':
            env=math.sin(math.pi*u)**.7
            ratchet=max(0,math.sin(t*math.tau*21))**12
            signal=env*(.16*bass+.4*filtered+.38*noise*ratchet)
        elif name=='titan_shutdown':
            env=math.sin(math.pi*u)**.6
            signal=env*(.25*math.sin(phase*(1-u*.65))+.25*filtered+.12*noise*(1-u))
        else:
            env=math.sin(math.pi*u)**.7
            signal=env*(.15*bass+.5*filtered+.16*noise)
        fade=min(1,t/.012,(seconds-t)/.04)
        samples.append(math.tanh(signal*1.7)*max(0,fade))
    peak=max(abs(x) for x in samples);gain=.72/max(.01,peak)
    return array('h',[round(x*gain*32767) for x in samples])
def main():
    report={}
    for i,(name,seconds) in enumerate(SPECS.items()):
        samples=synth(name,seconds,44000+i);p=ROOT/'src/assets/audio'/f'{name}.wav'
        with wave.open(str(p),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(samples.tobytes())
        report[name]={'seconds':seconds,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                      'peak':round(max(abs(x) for x in samples)/32767,4),'rms':round(math.sqrt(sum(x*x for x in samples)/len(samples))/32767,4)}
    out=ROOT/'.cache/titan-v40/audio.json';out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'sounds':len(report),'bytes':sum(x['bytes'] for x in report.values())}))
if __name__=='__main__':main()
