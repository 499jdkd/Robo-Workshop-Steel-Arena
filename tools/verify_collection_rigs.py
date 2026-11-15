"""Capture all authored robot artboards with the official Rive renderer."""
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image,ImageChops,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from robot_designs import DESIGNS

def main():
    output=ROOT/'.cache/rework-review/collection-rigs';output.mkdir(parents=True,exist_ok=True)
    cli=str(Path.home()/'.rive/bin/rive.exe');project=ROOT/'animation/rive/game_robot'
    result=subprocess.run([cli,'inspect',str(project),'--summary'],capture_output=True,encoding='utf8',check=True)
    inspected=json.loads(result.stdout);assert not inspected['problems'],inspected['problems']
    assert len(inspected['artboards'])>=30
    commands=[]
    for identity in DESIGNS:
        commands.extend([f'artboard {"Spark" if identity=="spark" else identity}','advance 1',f'screenshot {(output/(identity+".png")).as_posix()}'])
    command_file=output/'commands.txt';command_file.write_text('\n'.join(commands+['quit'])+'\n',encoding='utf8')
    run=subprocess.run([cli,str(project),f'--commands={command_file}'],capture_output=True,encoding='utf8',check=True)
    (output/'capture.log').write_text(run.stdout+run.stderr,encoding='utf8');assert 'err ' not in run.stdout
    sheet=Image.new('RGB',(8*180,4*210),'#0D1A30');draw=ImageDraw.Draw(sheet);bounds={}
    for i,identity in enumerate(DESIGNS):
        img=Image.open(output/f'{identity}.png').convert('RGB')
        delta=ImageChops.difference(img,Image.new('RGB',img.size,img.getpixel((0,0))));bbox=delta.getbbox()
        assert bbox is not None and bbox[2]-bbox[0]>60 and bbox[3]-bbox[1]>80,(identity,bbox)
        bounds[identity]=bbox
        img.thumbnail((174,183));x=(i%8)*180;y=(i//8)*210
        sheet.paste(img,(x+(180-img.width)//2,y));draw.text((x+8,y+185),identity,fill='white')
    sheet.save(output/'contact-sheet.png')
    (output/'summary.json').write_text(json.dumps({'artboards':len(DESIGNS),'visible_bounds':bounds},indent=2),encoding='utf8')
    print(output)

if __name__=='__main__':main()
