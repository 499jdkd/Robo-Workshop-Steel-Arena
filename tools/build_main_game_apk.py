"""Stage the complete game with Google test ads and the existing debug key."""

import argparse
import os
import subprocess
from pathlib import Path

from build_google_play import prepare_stage

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-number',type=int,default=21)
    args=parser.parse_args()
    stage=ROOT/f'.cache/game-test-v{args.build_number}'
    prepare_stage(ROOT,stage,number=args.build_number,version='0.2.0',ads_mode='test')
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1',JAVA_HOME=str(Path.home()/'java/17.0.13+11'))
    env['PATH']=str(Path.home()/'flutter/3.44.8/bin')+os.pathsep+str(Path(env['JAVA_HOME'])/'bin')+os.pathsep+env['PATH']
    # An upload key is deliberately not used for this sideloaded update.
    for key in list(env):
        if key.startswith('FLET_ANDROID_SIGNING_'):env.pop(key)
    output=ROOT/f'build/apk-game-v{args.build_number}'
    if (output/'clicker.apk').exists():raise RuntimeError('Retain the existing artifact; use a new number')
    log=ROOT/f'.cache/apk-game-v{args.build_number}.log'
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run([str(ROOT/'.venv/Scripts/flet.exe'),'build','apk',str(stage),'--output',str(output),'--build-number',str(args.build_number),'--build-version','0.2.0','--no-rich-output','-v'],cwd=stage,env=env,stdout=stream,stderr=subprocess.STDOUT,check=False)
    print('\n'.join(log.read_text(encoding='utf-8',errors='replace').splitlines()[-25:]))
    if result.returncode:raise SystemExit(result.returncode)
    print(f'Main game APK: {output / "clicker.apk"}')


if __name__=='__main__':main()
