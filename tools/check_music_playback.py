"""Observe actual browser playback in the main game with an isolated save.

This checks real media calls/completion, not speaker sound or Android behavior.
No forced autoplay policy, substituted audio player, or external account is used.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from run_volt_profile_comparison import python

ROOT=Path(__file__).resolve().parents[1]


def verify_events(events):
    music=[e for e in events if 'music_' in e.get('src','')]
    wins=[e for e in music if e['kind']=='playing' and 'music_victory' in e['src']]
    endings=[e for e in music if e['kind']=='ended' and 'music_victory' in e['src']]
    assert len(endings)==2,'Both compositions must reach the real media completion event'
    end1,end2=endings
    first_plays=[e for e in wins if e['ms']<end1['ms']]
    second=[e for e in wins if end1['ms']<e['ms']<end2['ms']]
    # The same bounded victory voice is reused for both songs. Separate the
    # playback cycles by their real completion events, not element identity.
    assert len(first_plays)==1 and len(second)==2, 'Expected one full victory, then a paused/resumed victory'
    first=first_plays[0]
    first_seconds=(end1['ms']-first['ms'])/1000
    assert 3.7<first_seconds<4.4,first_seconds
    interruptions=[e for e in music if e['id']==first['id'] and e['kind']=='pause' and first['ms']+100<e['ms']<end1['ms']-100]
    assert not interruptions,'A robot effect or screen change stopped the victory composition'
    assert second[1]['id']==second[0]['id'] and second[1]['pos']>second[0]['pos']+.15,'Pause/resume must preserve the position'
    assert 4.7<(end2['ms']-second[0]['ms'])/1000<5.6
    bg=[e for e in music if e['kind']=='playing' and 'music_victory' not in e['src']]
    assert any('music_arena' in e['src'] for e in bg),'Arena background did not load'
    assert any('music_workshop' in e['src'] and e['ms']>end1['ms'] and e['pos']>1 for e in bg),'Background did not resume from its saved position'
    active=set(); maximum=0
    for event in music:
        if 'music_victory' in event['src']:continue
        if event['kind']=='playing':active.add(event['id'])
        if event['kind'] in {'pause','ended'}:active.discard(event['id'])
        maximum=max(maximum,len(active))
    assert maximum==1,'Duplicate background instances overlap'
    gains=[e['gain'] for e in music if e['kind']=='gain' and 'music_workshop' in e['src']]
    assert len({round(g,5) for g in gains if 0<g<.115})>=4,'No real fade steps observed'
    storms=[e for e in events if e['kind']=='playing' and 'volt_storm.wav' in e['src']]
    assert storms and .29<=storms[-1]['pos']<.45,'Storm did not seek to its actual strike'
    assert not any(e['kind']=='playing' and '/victory.wav' in e.get('src','') for e in events),'Legacy SFX duplicated the music jingle'
    return {'status':'passed','real_main_game':True,'isolated_player_state':True,
            'first_victory_uninterrupted_seconds':round(first_seconds,3),
            'second_victory_resumed_at_seconds':round(second[1]['pos'],3),
            'victory_completion_events':len(endings),'max_simultaneous_backgrounds':maximum,
            'fade_gain_steps':sorted({round(g,5) for g in gains}),
            'storm_starts_at_seconds':round(storms[-1]['pos'],3),
            'physical_android_tested':False,'speaker_auditioned':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',default='volt-v36-music-live-02')
    parser.add_argument('--client',type=Path,default=ROOT/'.cache/volt-motion-v36/profile-client')
    parser.add_argument('--out-root',type=Path,default=ROOT/'.cache/volt-motion-v36')
    args=parser.parse_args()
    assert args.name.replace('-','').isalnum()
    out=args.out_root.resolve()/args.name
    assert not out.exists(),'Retain previous captures; select a new --name'
    out.mkdir(parents=True)
    if not (args.client/'rive').exists():
        shutil.copytree(ROOT/'.cache/volt-polish-v35/profile-client/rive',args.client/'rive')
    env=dict(os.environ,PYTHONUTF8='1');children=[];streams=[]
    try:
        for label,cmd in [
            ('metrics',python('collect_volt_metrics.py','--out',out/'frames.jsonl')),
            ('server',python('profile_interactive_game.py','--out',out,'--port',18580,'--music-check','--robot','volt')),
        ]:
            stream=(out/(label+'.log')).open('w',encoding='utf-8');streams.append(stream)
            children.append(subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=stream,stderr=stream,creationflags=subprocess.CREATE_NO_WINDOW))
        for _ in range(100):
            try:urlopen('http://127.0.0.1:18580',timeout=.3).close();break
            except OSError:
                if any(c.poll() is not None for c in children):raise RuntimeError('Helper stopped; inspect capture logs')
                time.sleep(.1)
        else:raise RuntimeError('Main-game server did not start')
        subprocess.run(python('capture_game_renderer.py','--name',args.name,'--port',18580,'--client',args.client,
                              '--width',390,'--height',844,'--seconds',27,'--audio-observe'),
                       cwd=ROOT,env=env,check=True,timeout=85)
        observed=ROOT/'.cache/rework-review'/args.name/'audio-events.json'
        report=verify_events(json.loads(observed.read_text()))
        report['events_file']=str(observed)
        (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)
    finally:
        for child in reversed(children):
            if child.poll() is None:child.terminate()
            child.wait(timeout=10)
        for stream in streams:stream.close()


if __name__=='__main__':main()
