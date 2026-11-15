"""Articulated collection rigs and thumbnails from the same editable vector art.

The scene uses real Rive geometry and data bindings, not a bitmap translated
around the screen. Each construction is independently authored below. Shared
weapon ports, face controls and actuator channels are the reusable interface.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from robot_designs import DESIGNS
from generate_spark import Rig

ROOT=Path(__file__).resolve().parents[2]
METAL=('FFF2F9FF','FFB7CBDE','FF58718B')
DARK=('FF354C68','FF15283F','FF091527')
GLOW=('FFE8FFFF','FF58E9FA','FF1499C5')

def lighten(c):
    c=c.lstrip('#');return 'FF'+''.join(f'{min(255,int(c[i:i+2],16)+55):02X}' for i in (0,2,4))

class CollectionRig:
    def __init__(self,template,design):
        self.d=design;self.root=deepcopy(template);self.rig=Rig();r=self.rig
        r.root=self.root;r.vm=self.root.find('ViewModel');r.instance=r.vm.find('ViewModelInstance');r.board=self.root.find('Artboard')
        r.ids={};r.next_id=4000;r.defaults={}
        r.fields={p.get('name'):p.get('id') for p in r.vm.findall('ViewModelPropertyNumber')}
        for n in list(r.board.findall('Node')):r.board.remove(n)
        for timeline in r.board.findall('LinearAnimation'):
            for obj in list(timeline.findall('KeyedObject')):timeline.remove(obj)
        r.board.set('name','Spark' if design['id']=='spark' else design['id'])
        r.board.set('originX','0');r.board.set('originY','0');r.board.set('clip','false')
        r.vm.set('name',f"Motion_{design['id']}")
        self.color=('FF'+design['color'][1:]);self.paint=(lighten(design['color']),self.color,'FF374D6D')
        self.robot=self.node(r.board,'Robot',x=210,y=276)
        for p,v in [('x',210),('y',276),('rotation',0)]:self.bind(self.robot,p,'Robot.'+p,v)
        self.body=self.node(self.robot,'Body')
        self.bind(self.body,'y','Body.y',0);self.bind(self.body,'rotation','Body.rotation',0)
        self.head_y=-110;self.head_x=0;self.head_w=125;self.head_h=90;self.eye='pair';self.heavy=False

    def node(self,p,n,**kw):return self.rig.element(p,'Node',n,**kw)
    def bind(self,n,p,key,v=0):
        n.set(p,str(v));self.rig.bind(n,p,key,v)
    def rect(self,p,n,x,y,w,h,c=METAL,r=8):return self.rig.shape(p,n,x,y,w,h,c,radius=r,outline='FF6F91B2')
    def oval(self,p,n,x,y,w,h,c=METAL):return self.rig.shape(p,n,x,y,w,h,c,ellipse=True)
    def path(self,p,n,points,c=METAL,stroke=0):return self.rig.path(p,n,points,c,stroke=stroke)
    def joint(self,p,n,x,y,index,rotation=0):
        node=self.node(p,n,x=x,y=y);self.bind(node,'rotation',f'joint{index}',rotation);return node
    def plate(self,p,n,x,y,w,h,color=None):
        self.rect(p,n+' face',x-2,y-3,w-8,h-8,color or self.paint,r=min(18,h/4))
        self.rect(p,n+' bevel',x,y,w,h,DARK,r=min(20,h/4))
    def bolts(self,p,y,xs):
        for i,x in enumerate(xs):
            self.rect(p,f'bolt slot {y} {i}',x,y,5,2,'FF5F7287',r=1)
            self.oval(p,f'bolt {y} {i}',x,y,9,9,METAL)
    def gear(self,p,x,y,index,size=18):
        n=self.joint(p,f'gear {index}',x,y,index)
        self.oval(n,f'gear hub {index}',0,0,size*.4,size*.4,GLOW)
        for i in range(8):
            tooth=self.node(n,f'gear tooth {index}-{i}',rotation=i*math.pi/4)
            self.rect(tooth,f'tooth plate {index}-{i}',0,-size*.7,size*.28,size*.55,METAL,r=2)
        self.oval(n,f'gear ring {index}',0,0,size*1.4,size*1.4,DARK)

    def wheels(self,count=2,tracks=False):
        base=self.node(self.robot,'Running gear',y=88)
        if tracks:
            # Sixteen individual tread shoes travel around the complete belt.
            for i in range(16):
                shoe=self.node(base,f'Tread shoe {i}')
                self.bind(shoe,'x',f'tread{i}X',-67+i*9)
                self.bind(shoe,'y',f'tread{i}Y',-29)
                self.bind(shoe,'rotation',f'tread{i}R',0)
                self.rect(shoe,f'Tread cleat {i}',0,0,12,7,METAL,r=2)
        for i in range(count):
            x=(i-(count-1)/2)*(145/max(1,count-1))
            wheel=self.node(base,f'Wheel {i}',x=x)
            self.bind(wheel,'rotation','wheelAngle',0)
            self.oval(wheel,f'Wheel hub {i}',0,0,14,14,self.paint)
            for s in range(6):
                spoke=self.node(wheel,f'Spoke {i}-{s}',rotation=s*math.pi/3)
                self.rect(spoke,f'Spoke metal {i}-{s}',0,-17,5,25,METAL,r=2)
            self.oval(wheel,f'Wheel inset {i}',0,0,49 if count==2 else 36,49 if count==2 else 36,DARK)
            self.oval(wheel,f'Tyre {i}',0,0,68 if count==2 else 48,68 if count==2 else 48,('FF5A6D80','FF0A1524'))
        if tracks:self.rect(base,'Track belt',0,0,218,73,DARK,r=34)

    def legs(self,count=2,span=135,long=False):
        # Offset phases are supplied by travelled distance, not frame count.
        for i in range(count):
            side=-1 if i<count/2 else 1
            row=i%max(1,count//2)
            hip=self.joint(self.robot,f'Leg hip {i}',side*(48+row*15),25+row*14,i)
            knee=self.joint(hip,f'Leg knee {i}',side*(span/2-45),35 if long else 23,i+8)
            self.plate(knee,f'Foot {i}',side*12,42 if long else 28,46 if count==2 else 30,19)
            self.rect(knee,f'Shin {i}',0,16,15,42 if long else 28,METAL,r=5)
            self.oval(knee,f'Knee bearing {i}',0,0,24,24,self.paint)
            self.rect(hip,f'Hip piston {i}',side*20,13,span/2-25,15,DARK,r=4)
            self.oval(hip,f'Hip joint {i}',0,0,24,24,METAL)

    def wings(self,fire=False,small=False):
        for side in (-1,1):
            wing=self.joint(self.robot,f'Wing {side}',side*48,-82,0 if side<0 else 1)
            for j in range(4):
                extent=90-j*12 if not small else 62-j*10
                self.path(wing,f'Flight feather {side}-{j}',[(side*5,j*12),(side*extent,-55+j*16),(side*(extent-9),-8+j*21),(side*14,35)],
                          ('FFFFD477','FFF3585E') if fire else self.paint if j%2 else METAL)
            self.oval(wing,f'Wing hinge {side}',0,0,26,26,DARK)

    def hover(self,rotors=0):
        for side in (-1,1):
            jet=self.node(self.robot,f'Hover flame {side}',x=side*48,y=85)
            self.bind(jet,'scaleY','jet',1)
            self.oval(jet,f'Ion plume {side}',0,15,22,52,('AA90F7FF','003694FD'))
            self.rect(self.robot,f'Hover nozzle {side}',side*48,76,38,23,DARK,r=8)
        for i in range(rotors):
            x=(-1 if i%2==0 else 1)*(90 if i<2 else 120);y=-70 if i<2 else 25
            rotor=self.joint(self.robot,f'Rotor {i}',x,y,4+i)
            self.oval(rotor,f'Rotor axle {i}',0,0,16,16,GLOW)
            self.rect(rotor,f'Rotor blade {i}',0,0,64,7,METAL,r=3)
            self.oval(self.robot,f'Rotor shroud {i}',x,y,76,26,DARK)

    def face(self):
        h=self.node(self.robot,'Head',x=self.head_x,y=self.head_y)
        self.bind(h,'y','Head.y',self.head_y);self.bind(h,'rotation','Head.rotation',0)
        gaze=self.node(h,'Gaze');self.bind(gaze,'x','lookX',0);self.bind(gaze,'y','lookY',0)
        eyes=self.node(gaze,'Eyes');self.bind(eyes,'scaleX','Eyes.scaleX',1);self.bind(eyes,'scaleY','Eyes.scaleY',1)
        if self.eye=='optic':
            self.oval(eyes,'Optic glint',-4,-7,9,9,'FFFFFFFF')
            self.oval(eyes,'Optic iris',0,-4,29,29,GLOW)
            self.oval(eyes,'Optic pupil',0,-4,47,47,('FF173E61','FF090F23'))
            self.oval(eyes,'Optic bezel',0,-4,62,62,self.paint)
        else:
            for side in (-1,1):
                self.rect(eyes,f'Eye glint {side}',side*self.head_w*.19-2,-7,4,8,'FFFAFFFF',r=2)
                self.rect(eyes,f'Eye {side}',side*self.head_w*.19,-2,15 if self.head_w<150 else 20,23,GLOW,r=7)
                brow=self.node(h,f'Brow {side}',x=side*self.head_w*.19,y=-26)
                self.bind(brow,'rotation','Brow L.rotation' if side<0 else 'Brow R.rotation',0)
                self.rect(brow,f'Brow light {side}',0,0,24,4,'FF65DFF5',r=2)
        for name,field,pts in [('Smile','Smile.opacity',[(-16,17),(-9,23),(1,25),(12,22),(17,17)]),('Focus mouth','Focus mouth.opacity',[(-13,22),(13,22)]),('Sad mouth','Sad mouth.opacity',[(-15,25),(-7,18),(7,18),(15,25)])]:
            node=self.node(gaze,name);self.bind(node,'opacity',field,1 if name=='Smile' else 0)
            self.path(node,name+' light',pts,'FF8CF6FF',stroke=4)
        shock=self.node(gaze,'Surprised mouth');self.bind(shock,'opacity','shock',0)
        self.oval(shock,'O mouth',0,20,13,18,'FFBAFFFF')
        self.rect(h,'Glass highlight',-self.head_w*.18,-self.head_h*.25,self.head_w*.45,5,'6686B6D4',r=2)
        self.rect(h,'Face glass',0,0,self.head_w-15,self.head_h-16,DARK,r=min(24,self.head_h/3))
        if self.d['construction'] in {'falcon','phoenix','ninja','gecko'}:
            self.path(h,'Angular helmet',[(-self.head_w/2,-self.head_h/2),(-20,-self.head_h/2-18),(self.head_w/2,-self.head_h/2+9),(self.head_w/2-8,self.head_h/2),(-self.head_w/2+5,self.head_h/2)],METAL)
        else:self.rect(h,'Helmet shell',0,0,self.head_w,self.head_h,METAL,r=min(28,self.head_h/3))
        self.rect(h,'Helmet lower bevel',0,5,self.head_w+8,self.head_h+3,self.paint,r=25)

    def arms(self,template):
        r=self.rig
        full_arms=self.d['construction'] in {'buggy','bioreactor','loader','juggernaut','gorilla','guardian','ninja'}
        for side,label in [(-1,'L'),(1,'R')]:
            if not full_arms and side<0:continue
            arm=self.node(self.robot,'Arm '+label,x=side*(83 if not self.heavy else 102),y=-36)
            self.bind(arm,'rotation','Arm '+label+'.rotation',side*-.05)
            fore=self.node(arm,'Forearm '+label,y=40)
            self.bind(fore,'rotation','Forearm '+label+'.rotation',0)
            if side>0:
                original=next(n for n in template.iter('Node') if n.get('name')=='Forearm R')
                for n in original:
                    if n.tag!='Node':continue
                    if n.get('name') in {'Palm','Plasma','Sniper','Fist','Rocket','Laser','Electric','Machinegun','Sword','Flame','Drone'} and (n.get('name')!='Palm' or full_arms):
                        copy=deepcopy(n)
                        for item in copy.iter():
                            if 'id' in item.attrib:
                                item.set('id',f'0:{r.next_id}');r.next_id+=1
                        fore.append(copy)
                from weapon_parts import add_weapons
                add_weapons(self,fore)
            else:
                self.rect(fore,'Left hand',0,38,40 if not self.heavy else 60,38,DARK,r=10)
            if full_arms:
                self.plate(fore,'Forearm '+label+' armor',0,10,35 if not self.heavy else 57,48)
                self.oval(arm,'Elbow '+label,0,40,25,25,METAL)
                self.rect(arm,'Arm '+label+' piston',0,17,19,42,DARK,r=6)
                self.oval(arm,'Shoulder '+label,0,0,39 if not self.heavy else 58,39 if not self.heavy else 58,self.paint)

    def build(self,template):
        b=self.body;k=self.d['construction']
        if k=='buggy':
            self.head_w=136;self.head_h=95;self.head_y=-106
            self.rect(b,'Bumper light',0,36,70,10,GLOW,r=5)
            self.plate(b,'Buggy hood',0,0,139,105)
            self.rect(b,'Curved chassis',0,63,197,38,METAL,r=17);self.wheels()
            self.gear(b,31,18,14)
            for side in (-1,1):self.oval(self.robot,f'Speaker {side}',side*77,-106,28,43,self.paint)
        elif k=='tesla':
            self.head_w=88;self.head_h=75;self.head_y=-85;self.eye='optic'
            for side in (-1,1):
                coil=self.joint(self.robot,f'Tesla mast {side}',side*76,-60,0 if side<0 else 1)
                for y in range(-55,6,12):self.oval(coil,f'Coil ring {side}-{y}',0,y,39,9,GLOW)
                self.rect(coil,f'Coil post {side}',0,-25,14,84,DARK,r=6)
            self.oval(b,'Electric orb',0,6,140,135,self.paint);self.hover()
        elif k=='bioreactor':
            self.head_y=-120;self.head_w=108;self.head_h=70
            self.rect(b,'Bio light',0,4,45,77,('FF9DFFD5','FF1A946C'),r=16)
            for i in range(5):self.oval(b,f'Bio bubble {i}',(-1)**i*12,-25+i*14,8,8,'FFB5FFE0')
            self.plate(b,'Glass reactor',0,5,90,115,METAL)
            for side in (-1,1):
                leaf=self.joint(self.robot,f'Leaf {side}',side*58,-115,side+2)
                self.oval(leaf,f'Leaf blade {side}',side*15,-20,26,66,self.paint)
            self.legs(2,long=True)
        elif k=='loader':
            self.heavy=True;self.head_y=-118;self.head_w=101;self.head_h=73
            for x in (-40,0,40):self.rect(b,f'Industrial vent {x}',x,0,19,60,DARK,r=4)
            self.plate(b,'Loader torso',0,5,180,132)
            self.rect(self.robot,'Loader roll cage',0,-158,185,20,self.paint,r=4)
            for x in (-84,84):self.rect(self.robot,f'Cage side {x}',x,-80,14,145,DARK,r=4)
            self.wheels(4,tracks=True);self.gear(b,50,34,14,23)
        elif k in {'reactor','gyro','sun','clock','storm','magnet','hologram'}:
            self.head_y=-48;self.head_w=96 if k!='sun' else 106;self.head_h=73;self.eye='optic' if k in {'gyro','clock','magnet'} else 'pair'
            diameter={'reactor':170,'gyro':176,'sun':150,'clock':160,'storm':140,'magnet':125,'hologram':134}[k]
            self.oval(b,'Core orb',0,-40,diameter,diameter,self.paint)
            for i in range({'reactor':3,'gyro':3,'sun':12,'clock':12,'storm':4,'magnet':3,'hologram':3}[k]):
                ring=self.joint(self.robot,f'Orbit mechanism {i}',0,-40,i%16,i*math.pi/6)
                if k in {'gyro','reactor'}:
                    self.path(ring,f'Orbit arc {i}',[(math.cos(a)*112,math.sin(a)*88) for a in [j*math.pi/12 for j in range(23)]],GLOW if i%2 else METAL,stroke=7)
                elif k=='sun':self.path(ring,f'Solar ray {i}',[(-8,-96),(0,-132),(8,-96)],self.paint)
                elif k=='clock':self.rect(ring,f'Clock index {i}',0,-102,8,20,GLOW,r=2)
                elif k=='magnet':self.path(ring,f'Magnet pole {i}',[(-28,-83),(-28,-113),(28,-113),(28,-83)],self.paint,stroke=14)
                elif k=='storm':self.path(ring,f'Lightning fork {i}',[(0,-65),(-14,-92),(12,-104),(0,-130)],GLOW,stroke=8)
                else:self.oval(ring,f'Hologram satellite {i}',0,-112,42,44,('5578DFFF','226D92DF'))
            self.hover()
        elif k=='crystal':
            self.head_y=-104;self.head_w=113;self.head_h=82;self.eye='optic'
            self.path(b,'Crystal reactor',[(-60,-57),(0,-85),(62,-50),(50,45),(0,68),(-53,42)],('FFE3FFFF','FF4899CC'))
            for side in (-1,1):
                fin=self.joint(self.robot,f'Ice fin {side}',side*63,-32,0 if side<0 else 1)
                self.path(fin,f'Ice shard {side}',[(0,0),(side*30,-70),(side*44,25),(0,67)],('FFEFFFFF','FF62B7DD'))
            self.hover()
        elif k in {'tank','artillery','driller'}:
            self.heavy=True;self.head_w=90;self.head_h=65;self.head_y=-70 if k!='driller' else -88
            self.plate(b,'Tank glacis',0,23,227,93)
            self.plate(b,'Turret',0,-40,157,75)
            if k=='artillery':
                for x in (-67,0,67):
                    launcher=self.joint(self.robot,f'Rocket pod {x}',x,-130,0 if x<0 else 1)
                    for y in (-14,14):self.oval(launcher,f'Missile port {x}-{y}',0,y,22,22,('FFFFDB99','FFD44B58'))
                    self.rect(launcher,f'Pod armor {x}',0,0,49,83,DARK,r=9)
            elif k=='driller':
                drill=self.joint(self.robot,'Borer',108,22,4)
                self.path(drill,'Drill cone',[(0,-43),(64,0),(0,43)],METAL)
                for x in (7,20,33):self.path(drill,f'Borer helix {x}',[(x,-33+x/3),(x+12,22-x/4)],self.paint,stroke=8)
            else:
                self.rect(b,'Cannon tube',92,-72,113,24,METAL,r=7);self.oval(b,'Muzzle cap',148,-72,22,32,DARK)
            self.wheels(4,tracks=True)
        elif k in {'spider','beetle','transformer'}:
            self.head_y=-65 if k=='spider' else -70;self.head_w=95 if k=='beetle' else 112;self.head_h=67;self.eye='optic' if k=='spider' else 'pair'
            if k=='spider':self.oval(b,'Arachnid carapace',0,-12,155,120,self.paint);self.legs(6,span=225)
            elif k=='beetle':
                for side in (-1,1):
                    shell=self.joint(self.robot,f'Beetle wing case {side}',side*4,-45,0 if side<0 else 1)
                    self.oval(shell,f'Armored elytron {side}',side*40,35,92,152,self.paint)
                self.path(self.robot,'Scarab horn',[(-10,-100),(0,-147),(18,-117),(10,-81)],METAL);self.legs(4,span=180)
            else:
                self.path(b,'Conversion shell',[(-77,-60),(0,-95),(79,-50),(74,45),(0,74),(-72,42)],self.paint)
                for side in (-1,1):
                    panel=self.joint(self.robot,f'Conversion armor {side}',side*65,-35,2 if side<0 else 3)
                    self.plate(panel,f'Folding armor {side}',side*12,10,46,111,METAL)
                self.legs(6,span=202)
        elif k in {'falcon','phoenix'}:
            self.head_y=-105;self.head_w=92;self.head_h=77
            self.path(b,'Avian breast',[(-52,-69),(47,-70),(65,13),(0,60),(-54,14)],self.paint)
            self.path(self.robot,'Avian beak',[(33,-99),(76,-81),(32,-67)],('FFFFE8A1','FFF0A13F'))
            self.wings(fire=k=='phoenix');self.hover()
            self.path(self.robot,'Tail feather',[(-18,56),(0,109),(22,53)],METAL)
        elif k=='medic':
            self.head_y=-49;self.head_w=92;self.head_h=70;self.eye='optic'
            self.rect(b,'Medical cross vertical',0,28,15,44,'FFB2FFDE',r=4)
            self.rect(b,'Medical cross horizontal',0,28,44,15,'FFB2FFDE',r=4)
            self.oval(b,'Repair sphere',0,-11,156,164,('FFF2FFF9','FF60A899'));self.hover(rotors=4)
        elif k=='tripod':
            self.head_y=-115;self.head_w=99;self.head_h=93;self.eye='optic'
            self.plate(b,'Optical turret',0,-13,107,100)
            self.rect(b,'Sniper rail',82,-47,133,19,METAL,r=5)
            self.oval(b,'Precision muzzle',148,-47,17,26,DARK)
            self.legs(3,span=205,long=True)
            self.gear(b,-22,11,14)
        elif k in {'hound','gecko','siege'}:
            self.head_y=-67 if k!='siege' else -108;self.head_x=80 if k!='siege' else 0;self.head_w=99 if k!='siege' else 92;self.head_h=65;self.heavy=k=='siege'
            self.plate(b,'Quadruped spine',0,12,201 if k!='gecko' else 163,100 if k=='siege' else 72)
            self.legs(4,span=170 if k!='siege' else 225,long=k=='siege')
            if k=='hound':
                for x in (54,103):self.path(self.robot,f'Hound ear {x}',[(x-12,-101),(x,-138),(x+13,-101)],self.paint)
                tail=self.joint(self.robot,'Hound tail',-100,8,4);self.path(tail,'Tail mast',[(0,0),(-35,-37),(-47,-25)],METAL)
            elif k=='gecko':
                tail=self.joint(self.robot,'Gecko tail',-75,21,4)
                self.path(tail,'Adaptive tail',[(0,-18),(-69,-3),(-118,-33),(-91,17),(-40,25),(0,12)],self.paint)
                for x in (-45,0,45):self.oval(b,f'Adaptive armor cell {x}',x,-2,29,28,GLOW)
            else:
                self.rect(self.robot,'Siege rail barrel',90,-82,126,29,DARK,r=6)
                self.rect(self.robot,'Siege cannon',24,-89,150,58,METAL,r=8)
                self.gear(b,-44,5,14,25)
        elif k=='serpent':
            self.head_x=108;self.head_y=8;self.head_w=90;self.head_h=73;self.eye='optic'
            for i in range(7):
                segment=self.joint(self.robot,f'Serpent segment {i}',105-i*35,55,i)
                self.bind(segment,'y',f'segmentY{i}',55)
                self.oval(segment,f'Segment core {i}',0,0,26,32,GLOW)
                self.oval(segment,f'Segmented shell {i}',0,0,43-i*2,56-i*3,self.paint if i%2 else METAL)
            for x in (94,120):self.path(self.robot,f'Fang {x}',[(x,40),(x+3,70),(x+14,38)],METAL)
        elif k=='octopus':
            self.head_y=-104;self.head_w=121;self.head_h=96
            self.oval(b,'Cephalopod chamber',0,-52,142,169,self.paint)
            for i in range(8):
                arm=self.joint(self.robot,f'Tentacle {i}',(i-3.5)*14,9,i)
                self.path(arm,f'Segmented tentacle {i}',[(0,0),((i-3.5)*20,36),((i-3.5)*31,69),((i-3.5)*27,96)],METAL,stroke=13)
                for j in range(3):self.oval(arm,f'Tentacle joint {i}-{j}',(i-3.5)*(8+j*8),25+j*24,17,17,self.paint)
        elif k=='cloak':
            self.head_y=-95;self.head_w=89;self.head_h=76;self.eye='optic'
            self.path(b,'Cloak mantle',[(-58,-120),(0,-163),(64,-110),(76,77),(0,36),(-76,74)],('FFAAAFEA','FF232744'))
            self.hover()
        elif k in {'juggernaut','gorilla','guardian','ninja'}:
            self.heavy=k!='ninja';self.head_w=108 if k!='ninja' else 93;self.head_h=77;self.head_y=-135 if k!='gorilla' else -100
            self.plate(b,'Chest armor',0,-14,173 if k!='ninja' else 104,136 if k!='ninja' else 118)
            self.rect(b,'Reactor strip',0,-29,40 if k!='ninja' else 19,39,GLOW,r=9)
            self.legs(2,long=True)
            if k=='guardian':
                self.path(self.robot,'Great shield',[(22,-117),(108,-145),(142,-86),(134,43),(84,91),(31,45)],('FF9CEAFF','FF3169B2'))
                self.path(self.robot,'Shield inset',[(46,-91),(105,-112),(116,-76),(109,23),(83,52),(56,21)],GLOW,stroke=5)
            if k=='ninja':
                scarf=self.joint(self.robot,'Scarf',-44,-119,4)
                self.path(scarf,'Scarf ribbon',[(0,0),(-77,2),(-112,30),(-50,20)],self.paint)
                self.path(self.robot,'Ninja antenna',[(-25,-162),(0,-193),(17,-162)],self.paint)
            if k=='gorilla':
                for x in (-108,108):self.plate(self.robot,f'Giant power knuckle {x}',x,38,67,84)
            if k=='juggernaut':
                for side in (-1,1):self.plate(self.robot,f'Titan pauldron {side}',side*98,-67,68,75)
        self.face();self.arms(template)
        for field,x,y in [('modArmor',-44,-9),('modCore',0,-22),('modDrive',-55,68),('modDefense',52,-12),('modGadget',30,-160)]:
            module=self.node(self.robot,field,x=x,y=y);self.bind(module,'opacity',field,0)
            self.oval(module,field+' light',0,0,20,20,('FFE8FFFF','FF58E9FA'))
            self.rect(module,field+' case',0,0,28,32,r=7)
        self.rig.instance.find('ViewModelInstanceColor').set('propertyValue',self.color)
        for stop in self.robot.iter('GradientStop'):
            if stop.get('colorValue')==self.color:
                ET.SubElement(stop,'DataBindContext',propertyKey='38',sourcePathIds='0:10-0:25000')
        shield=self.node(self.robot,'Shield');self.bind(shield,'opacity','Shield.opacity',0)
        self.path(shield,'Energy shield',[(76,-138),(142,-115),(152,-20),(110,35),(65,-12)],'AA6EF1FF',stroke=8)
        aura=self.node(self.robot,'Charge aura');self.bind(aura,'opacity','Charge aura.opacity',0)
        self.oval(aura,'Energy halo',0,-50,280,330,'2246D8FF')
        self.oval(self.robot,'Contact shadow',0,126,215,18,'6620344B')
        # Keep the face above armor and limbs; the first sibling is foreground.
        h=next(n for n in self.robot if n.get('name')=='Head');self.robot.remove(h);self.robot.insert(0,h)
        # All artboards expose the same optional actuator channels.
        for i in range(16):self.rig.field(f'joint{i}',0)
        for i in range(8):self.rig.field(f'segmentY{i}',55)
        for name in ('cryo','ion','blaster','magnetic','grenade','emp','drill','disc','repair'):
            self.rig.field(name,0)
        # Set artboard-specific portrait defaults, also read by the host profile.
        prop=self.rig.fields['Head.y']
        next(n for n in self.rig.instance if n.get('viewModelPropertyId')==prop).set('propertyValue',str(self.head_y))
        return self.root

def extend_collection(template):
    all_root=ET.Element('Rive',version='1',kind='fragment');profiles={}
    for i,d in enumerate(DESIGNS.values()):
        model=CollectionRig(template,d);root=model.build(template)
        profiles[d['id']]={'construction':d['construction'],'mobility':d['mobility'],'headY':model.head_y,'headX':model.head_x,'class':d['class']}
        export_svg(root,ROOT/'src/assets/art/portraits'/f"{d['id']}.svg")
        root.find('Artboard').set('x',str((i%8)*500))
        root.find('Artboard').set('y',str((i//8)*520))
        for node in root.iter():
            for key,value in list(node.attrib.items()):
                node.set(key,re.sub(r'0:(\d+)',lambda m:f'0:{int(m[1])+i*100000}',value))
        all_root.extend(list(root))
    target=ROOT/'extensions/flet_rive/lib/src/robot/robot_profiles.dart'
    target.write_text('// Generated from robot_designs.py and the authored Rive rigs.\nconst robotProfiles = <String, Map<String, dynamic>>'+json.dumps(profiles,ensure_ascii=False,indent=2)+';\n',encoding='utf8')
    return all_root

def export_svg(root,path):
    """Static thumbnail export of our own editable Rive shapes, not new artwork."""
    path.parent.mkdir(parents=True,exist_ok=True)
    defs=[];index=0
    def color(value):
        value=value or 'FFFFFFFF';return '#'+value[2:],int(value[:2],16)/255
    def paint(node,stroke=False):
        nonlocal index
        values=[]
        for p in node.findall('Stroke' if stroke else 'Fill'):
            solid=p.find('SolidColor');g=p.find('LinearGradient')
            if solid is not None:
                c,a=color(solid.get('colorValue'));values.append((c,a,p.get('thickness','0')))
            elif g is not None:
                index+=1;name='g'+str(index)
                stops=''.join(f'<stop offset="{s.get("position")}" stop-color="{color(s.get("colorValue"))[0]}" stop-opacity="{color(s.get("colorValue"))[1]}"/>' for s in g)
                defs.append(f'<linearGradient id="{name}" x1="0" y1="0" x2="1" y2="1">{stops}</linearGradient>')
                values.append((f'url(#{name})',1,p.get('thickness','0')))
        return values
    def visit(node):
        if node.tag not in {'Node','Shape','Artboard'}:return ''
        a=node.attrib
        if float(a.get('opacity',1))==0:return ''
        tr=f'translate({a.get("x",0)} {a.get("y",0)}) rotate({float(a.get("rotation",0))*180/math.pi}) scale({a.get("scaleX",1)} {a.get("scaleY",1)})'
        children=''.join(visit(n) for n in reversed(list(node)))
        if node.tag=='Shape':
            geom=next((n for n in node if n.tag in {'Rectangle','Ellipse','PointsPath'}),None)
            if geom is not None:
                w=float(geom.get('width',0));h=float(geom.get('height',0))
                shape=(f'<rect x="{-w/2}" y="{-h/2}" width="{w}" height="{h}" rx="{geom.get("cornerRadiusTL",0)}"' if geom.tag=='Rectangle' else f'<ellipse cx="0" cy="0" rx="{w/2}" ry="{h/2}"' if geom.tag=='Ellipse' else '<path d="M '+' L '.join(f'{v.get("x",0)} {v.get("y",0)}' for v in geom)+(' Z' if geom.get('isClosed')!='false' else '')+'"')
                children=''.join(shape+f' fill="{c}" fill-opacity="{alpha}"/>' for c,alpha,_ in paint(node))
                children+=''.join(shape+f' fill="none" stroke="{c}" stroke-opacity="{alpha}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>' for c,alpha,width in paint(node,True))
        return f'<g transform="{tr}" opacity="{a.get("opacity",1)}">{children}</g>'
    content=visit(root.find('Artboard'))
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="440" viewBox="0 0 420 440"><defs>{"".join(defs)}</defs>{content}</svg>',encoding='utf8')
