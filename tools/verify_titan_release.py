"""Check Titan-only artwork, preserved game data and the final main-game APK."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import wave
import zipfile
import xml.etree.ElementTree as ET
from verify_volt_release import ability_rows, xml_digest, unchanged_file, file_hash

ROOT=Path(__file__).resolve().parents[1]
BASELINE=ROOT/'.cache/titan-v40/baseline'
NATIVE_MARKERS=('applyTitanPose','paintTitanEffects','drawTitanModel','_TitanRaster','titan_ram','titan_quake','titan_bastion')

def verify_scope(root=ROOT,baseline=BASELINE):
    root,baseline=Path(root),Path(baseline)
    old=ET.parse(baseline/'animation/rive/game_robot/scene.rml').getroot()
    new=ET.parse(root/'animation/rive/game_robot/scene.rml').getroot()
    structures={}
    for kind,excluded in [('Artboard','titan'),('ViewModel','Motion_titan')]:
        a={n.get('name'):xml_digest(n) for n in old.findall(kind)}
        b={n.get('name'):xml_digest(n) for n in new.findall(kind)}
        assert len(a)==32 and a.keys()==b.keys()
        assert a[excluded]!=b[excluded],f'Titan {kind} was not redesigned'
        assert all(a[k]==b[k] for k in a if k!=excluded),f'Another {kind} changed'
        structures[kind]={'preserved_count':31,'preserved':{k:a[k] for k in a if k!=excluded}}
    before,after=ability_rows(baseline/'src/robot_abilities.py'),ability_rows(root/'src/robot_abilities.py')
    assert all(before[k]==after[k] for k in before if k!='titan')
    portraits={}
    for name in before:
        if name=='titan':continue
        relative=f'src/assets/art/portraits/{name}.svg'
        portraits[name]=unchanged_file(root/relative,baseline/relative,relative)
    assert (root/'src/assets/art/portraits/titan.svg').read_bytes()!=(baseline/'src/assets/art/portraits/titan.svg').read_bytes()
    audio={}
    for p in (baseline/'src/assets/audio').iterdir():
        if p.is_file():audio[p.name]=unchanged_file(root/'src/assets/audio'/p.name,p,p.name)
    assert len(audio)==49
    added={}
    for p in sorted((root/'src/assets/audio').glob('titan_*.wav')):
        with wave.open(str(p),'rb') as f:
            assert f.getsampwidth()==2 and f.getnchannels()==1 and f.getframerate()==22050
            duration=f.getnframes()/f.getframerate()
            assert .2<=duration<=2
        added[p.name]={'bytes':p.stat().st_size,'sha256':file_hash(p),'duration':duration}
    assert len(added)==8 and len({x['sha256'] for x in added.values()})==8
    preserved={}
    for name in ['combat_rules.py','robot_arena.py','armory.py','gameplay.py','local_store.py','network_config.py']:
        preserved[name]=unchanged_file(root/'src'/name,baseline/'src'/name,name)
    riv=unchanged_file(root/'src/assets/animation/game_robot.riv',baseline/'src/assets/animation/game_robot.riv','Published signed Rive file')
    board=next(x for x in new.findall('Artboard') if x.get('name')=='titan')
    return {'artboards_and_models':structures,'other_ability_rows':31,'other_portraits':portraits,
            'preserved_audio':audio,'new_titan_audio':added,'preserved_game_and_storage':preserved,
            'published_rive':riv,'titan_shapes':len(list(board.iter('Shape')))}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-number',type=int,default=42)
    parser.add_argument('--source-only',action='store_true')
    args=parser.parse_args();out=ROOT/f'build/titan-verification-v{args.build_number}'
    out.mkdir(parents=True,exist_ok=True)
    report={'build':args.build_number,'status':'checking','baseline':'72a1cce81e21196c15577e8772f0361f9a9ccc48','physical_android_tested':False}
    try:
        report['scope']=verify_scope()
        if not args.source_only:
            apk=ROOT/f'build/apk-game-v{args.build_number}/clicker.apk'
            report['apk']={'bytes':apk.stat().st_size,'sha256':file_hash(apk),'native_markers':{}}
            with zipfile.ZipFile(apk) as archive:
                for abi in ['arm64-v8a','armeabi-v7a','x86_64']:
                    data=archive.read(f'lib/{abi}/libapp.so')
                    for name in NATIVE_MARKERS:assert name.encode() in data,(abi,name)
                    report['apk']['native_markers'][abi]=list(NATIVE_MARKERS)
                with zipfile.ZipFile(io.BytesIO(archive.read('assets/app.zip'))) as app:
                    for excluded in ['fix','some','tempCodeRunnerFile']:
                        assert excluded+'.py' not in app.namelist()
                        assert excluded+'.pyc' not in app.namelist()
                    assets=[ROOT/'src/assets/art/portraits/titan.svg',
                            ROOT/'src/assets/animation/game_robot.riv',
                            *sorted((ROOT/'src/assets/audio').iterdir())]
                    report['apk']['packaged_assets']={}
                    for source in assets:
                        if not source.is_file():continue
                        name='assets/'+source.relative_to(ROOT/'src/assets').as_posix()
                        assert app.read(name)==source.read_bytes(),name
                        report['apk']['packaged_assets'][name]=file_hash(source)
                    report['apk']['temporary_and_excluded_modules_absent']=True
        report['status']='passed'
    finally:
        (out/'scope-and-package.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'titan_shapes':report['scope']['titan_shapes'],
                      'other_robots_preserved':31,'old_audio_preserved':49,'new_audio':8,
                      'physical_android_tested':False}))
if __name__=='__main__':main()
