"""Titan: a siege colossus with telescoping pile-driver arms and hydraulic legs.

Every plate, rod, cooling louvre, pressure gauge and finger is vector artwork.
The existing weapon socket is retained inside the right forearm.
"""
import math
from volt_art import fit_materials, silhouette, cable, forward

IVORY = ('FFFFF1CC', 'FFCDBD91', 'FF716C59')
GOLD = ('FFFFDC79', 'FFD39B36', 'FF775022')
STEEL = ('FFDBE7E9', 'FF8C9FA7', 'FF3B505D')
DARK = ('FF3D4B51', 'FF1D2A32', 'FF0A141D')
LIGHT = ('FFFFF8D2', 'FFFFCF64', 'FFE87F32')
EDGE = 'FFFFE7AB'

def plate(r,p,n,pts,color=IVORY,radius=4):
    return silhouette(r,p,n,pts,color,radius)

def bolt(r,p,n,x,y,size=7):
    r.path(p,n+' slot',[(x-size*.23,y),(x+size*.23,y)],'FF16242C',stroke=1.5)
    r.oval(p,n+' inset',x,y,size*.55,size*.55,DARK)
    r.oval(p,n+' cap',x,y,size,size,STEEL)
    r.oval(p,n+' socket',x,y,size+3,size+3,DARK)

def glow(r,p,n,x,y,w,h,field='titanPower'):
    group=r.node(p,n,x=x,y=y);r.bind(group,'opacity',field,1)
    r.rect(group,n+' light',0,0,w,h,LIGHT,r=min(w,h)*.3)
    return group

def ring(r,p,n,x,y,size,index):
    rotor=r.joint(p,n,x,y,index)
    for i in range(8):
        a=i*math.tau/8
        tooth=r.node(rotor,n+f' tooth {i}',x=math.cos(a)*size*.39,y=math.sin(a)*size*.39,rotation=a)
        r.rect(tooth,n+f' machined tooth {i}',0,0,size*.2,size*.12,STEEL,r=1)
    r.oval(rotor,n+' hub',0,0,size*.3,size*.3,DARK)
    r.oval(rotor,n+' bearing',0,0,size*.66,size*.66,GOLD)
    r.oval(rotor,n+' recess',0,0,size*.9,size*.9,DARK)
    return rotor

def chassis(r):
    r.heavy=True;r.head_w=104;r.head_h=65;r.head_y=-112
    b=r.body
    r.bind(b,'scaleX','bodyscaleX',1);r.bind(b,'scaleY','bodyscaleY',1)
    # A pressure engine, not Volt's luminous Tesla core.
    gauge=r.node(b,'Titan central pressure engine',y=-12)
    needle=r.joint(gauge,'Titan pressure needle',0,0,4)
    plate(r,needle,'Titan gauge indicator',[(-3,4),(0,-20),(3,4)],LIGHT,1)
    bolt(r,needle,'Titan gauge spindle',0,2,6)
    cable(r,gauge,'Pressure glass reflection',[(-24,-9),(-17,-21),(-4,-25)],'77FFFFFF',2.1)
    for side in (-1,1):
        bolt(r,gauge,f'Pressure engine collar {side}',side*29,22,5)
    for i in range(7):
        a=-2.6+i*.34
        mark=r.node(gauge,f'Pressure scale {i}',rotation=a)
        r.rect(mark,f'Pressure tick {i}',0,-24,2.5,6,EDGE,r=.5)
    for side in (-1,1):
        glow(r,gauge,f'Pressure window {side}',side*17,12,7,10,'titanPress')
    r.oval(gauge,'Pressure dial dark glass',0,0,58,60,DARK)
    plate(r,gauge,'Pressure engine bevel',[(-34,-28),(-16,-39),(18,-38),(35,-23),(34,26),(13,37),(-20,34),(-36,18)],STEEL,5)
    plate(r,gauge,'Pressure engine deep housing',[(-40,-33),(-18,-44),(22,-42),(42,-24),(40,31),(15,43),(-24,39),(-43,19)],DARK,6)
    for side in (-1,1):
        # Floating chest plates and recessed exhaust slots.
        wing=r.joint(b,f'Titan chest shutter {side}',side*57,-15,5 if side<0 else 6)
        for i in range(4):
            r.rect(wing,f'Chest cooling cut {side}-{i}',side*2,-14+i*10,22,3,DARK,r=1)
        glow(r,wing,f'Chest pressure lamp {side}',side*-11,-22,5,26,'titanPress')
        plate(r,wing,f'Raised chest flank {side}',[(-22,-39),(18,-35),(25,-14),(20,32),(-17,37),(-27,19)],IVORY,5)
        bolt(r,b,f'Torso fastener {side}',side*66,25)
        for i in range(3):
            cable(r,b,f'Torso machined seam {side}-{i}',[(side*(74-i*3),-30+i*4),(side*(78-i*3),-20+i*4)],'FF8A784D',1.2)
        plate(r,b,f'Chest side bevel {side}',[(side*44,-48),(side*81,-36),(side*87,10),(side*72,43),(side*52,39),(side*64,3)],GOLD,5)
        cable(r,b,f'Chest oil hose {side}',[(side*38,-46),(side*49,-58),(side*69,-49),(side*75,-35)],DARK,6)
        cable(r,b,f'Chest hose highlight {side}',[(side*39,-47),(side*50,-57),(side*68,-48)],STEEL,1.5)
    plate(r,b,'Titan torso top bevel',[(-77,-44),(-49,-67),(45,-69),(79,-43),(54,-47),(-48,-49)],IVORY,5)
    plate(r,b,'Titan armored barrel torso',[(-63,-62),(56,-63),(87,-36),(86,18),(63,49),(-55,49),(-86,22),(-88,-35)],IVORY,9)
    plate(r,b,'Titan torso thickness',[(-67,-68),(62,-68),(94,-39),(94,23),(67,57),(-60,56),(-95,25),(-97,-39)],DARK,10)
    # Independent weight-bearing legs; no hover or stock running gear.
    for side,label in [(-1,'L'),(1,'R')]:
        leg=r.node(r.robot,'Titan leg '+label,x=side*48,y=40)
        r.bind(leg,'x','titanLegX'+label,side*48)
        r.bind(leg,'y','titanLegY'+label,40)
        r.bind(leg,'rotation','joint8' if side<0 else 'joint9',0)
        foot=r.node(leg,'Titan foot '+label,y=62)
        r.bind(foot,'rotation','joint14' if side<0 else 'joint15',0)
        for i in range(3):
            plate(r,foot,f'Foot armored toe {label}-{i}',[(-30+i*21,0),(-12+i*21,-3),(-7+i*21,18),(-27+i*21,22)],STEEL,3)
            r.rect(foot,f'Toe sole tread {label}-{i}',-20+i*21,19,17,5,DARK,r=1)
        plate(r,foot,'Titan broad sole '+label,[(-38,-6),(27,-9),(40,2),(38,21),(-33,25),(-42,14)],DARK,5)
        for x in (-13,13):
            r.rect(leg,f'Leg piston chrome {label}-{x}',x,29,7,43,STEEL,r=2)
            r.rect(leg,f'Leg oil sleeve {label}-{x}',x,6,15,31,DARK,r=4)
        bolt(r,leg,'Knee axle '+label,0,27,15)
        plate(r,leg,'Titan kneecap '+label,[(-22,5),(22,3),(27,20),(18,39),(-20,39),(-28,21)],IVORY,5)
        glow(r,leg,'Knee status '+label,0,17,17,4)
        r.oval(leg,'Hip load bearing '+label,0,0,51,43,DARK)
        plate(r,r.robot,'Titan hip apron '+label,[(side*20,33),(side*69,30),(side*77,56),(side*35,63)],GOLD,4)
    plate(r,r.robot,'Titan belt plate',[(-28,36),(28,36),(32,53),(18,63),(-20,63),(-32,52)],STEEL,4)
    # Back-mounted flywheel and split radiator banks animate independently.
    for side in (-1,1):
        bank=r.node(r.robot,f'Titan radiator bank {side}',x=side*64,y=-91)
        r.bind(bank,'rotation','titanVentL' if side<0 else 'titanVentR',0)
        for i in range(4):
            plate(r,bank,f'Exhaust vane {side}-{i}',[(-13,-18+i*11),(14,-20+i*11),(17,-11+i*11),(-11,-8+i*11)],STEEL,2)
        r.rect(bank,f'Radiator spine {side}',0,4,34,67,DARK,r=4)
    fly=ring(r,r.robot,'Titan back counterweight',0,-64,145,7)
    r.robot.remove(fly);r.robot.append(fly)
    fit_materials(r.robot)

def face(r):
    h=r.node(r.robot,'Head',y=r.head_y)
    r.bind(h,'y','Head.y',r.head_y);r.bind(h,'rotation','Head.rotation',0)
    gaze=r.node(h,'Gaze');r.bind(gaze,'x','lookX',0);r.bind(gaze,'y','lookY',0)
    eyes=r.node(gaze,'Eyes',y=-5);r.bind(eyes,'scaleX','Eyes.scaleX',1);r.bind(eyes,'scaleY','Eyes.scaleY',1)
    live=r.node(eyes,'Titan eye power');r.bind(live,'opacity','titanPower',1)
    for side in (-1,1):
        r.rect(live,f'Titan eye catchlight {side}',side*19-3,-2,4,3,'FFFFFFFF',r=1)
        r.rect(live,f'Titan amber eye {side}',side*18,0,18,11,LIGHT,r=3)
        brow=r.node(h,f'Brow {side}',x=side*18,y=-16)
        r.bind(brow,'rotation','Brow L.rotation' if side<0 else 'Brow R.rotation',0)
        plate(r,brow,f'Titan brow metal {side}',[(-15,-4),(15,-4),(12,3),(-12,4)],IVORY,2)
        bolt(r,h,f'Helmet temple {side}',side*45,-4,7)
        plate(r,h,f'Helmet carved side {side}',[(side*40,-24),(side*48,-19),(side*48,12),(side*31,28),(side*34,17),(side*40,9)],
              ('FFF9EDD0','FF908875','FF4B5653') if side>0 else ('FFFFFFFF','FFDED7B8','FF8E9D92'),2)
        cable(r,h,f'Helmet edge reflection {side}',[(side*41,-23),(side*44,-16),(side*43,8)],EDGE,1.6)
    for field,name,pts in [('Smile.opacity','Smile',[(-13,13),(0,17),(13,13)]),('Focus mouth.opacity','Focus mouth',[(-10,15),(10,15)]),('Sad mouth.opacity','Sad mouth',[(-12,19),(0,14),(12,19)])]:
        n=r.node(h,name);r.bind(n,'opacity',field,1 if name=='Smile' else 0)
        cable(r,n,'Titan '+name,pts,EDGE,2.2)
    for x in (-16,-8,0,8,16):
        r.rect(h,f'Titan jaw grille {x}',x,25,3,7,DARK,r=1)
    plate(r,h,'Titan machined chin bevel',[(-28,30),(26,30),(18,35),(-20,35)],STEEL,2)
    plate(r,h,'Titan inset visor',[(-34,-21),(34,-21),(38,-8),(31,17),(-30,17),(-39,-6)],DARK,6)
    plate(r,h,'Titan helmet crown light',[(-44,-30),(-20,-42),(22,-42),(47,-28),(22,-32),(-21,-32)],GOLD,3)
    plate(r,h,'Titan helmet faceplate',[(-45,-27),(-24,-39),(23,-38),(48,-24),(48,13),(25,33),(-28,33),(-49,13)],IVORY,7)
    plate(r,h,'Titan helmet dark depth',[(-49,-30),(-26,-43),(26,-43),(53,-25),(54,17),(27,39),(-31,39),(-55,17)],DARK,8)
    r.rect(h,'Titan neck hydraulic pivot',0,38,46,19,STEEL,r=5)
    fit_materials(h)

def finish_arms(r):
    for side,label in [(-1,'L'),(1,'R')]:
        arm=next(n for n in r.robot if n.get('name')=='Arm '+label)
        arm.set('x',str(side*99));arm.set('y','-55')
        fore=next(n for n in arm if n.get('name')=='Forearm '+label);fore.set('y','48')
        # Remove stock armor, retain only the real optional weapon assemblies.
        for node in list(arm):
            if node is not fore and node.tag!='DataBindContext':arm.remove(node)
        for node in list(fore):
            if node.tag!='Node' and node.tag!='DataBindContext':fore.remove(node)
        wrist=forward(fore,r.node(fore,'Titan piledriver '+label))
        r.bind(wrist,'y','titanHammer'+label,0)
        for i in range(3):
            plate(r,wrist,f'Titan impact knuckle {label}-{i}',[(-30+i*22,53),(-12+i*22,52),(-8+i*22,75),(-26+i*22,80)],STEEL,3)
            bolt(r,wrist,f'Knuckle pin {label}-{i}',-21+i*22,62,6)
        glow(r,wrist,'Titan knuckle pressure '+label,0,46,43,5,'titanPress')
        for i in range(3):
            cable(r,wrist,f'Piledriver wear line {label}-{i}',[(-25+i*8,-3),(-19+i*8,1)],'FF8F805B',1.2)
        plate(r,wrist,'Titan forearm left bevel '+label,[(-34,-6),(-27,0),(-28,39),(-18,51),(-28,55),(-37,42)],STEEL,3)
        plate(r,wrist,'Titan forearm right relief '+label,[(27,-12),(38,-2),(35,44),(24,54),(20,49),(27,38)],('FFDBCE9F','FF8D774C','FF504836'),3)
        for x in (-20,20):
            r.rect(wrist,f'Piledriver chrome rail {label}-{x}',x,26,7,48,STEEL,r=2)
            r.rect(wrist,f'Piledriver rod collar {label}-{x}',x,12,14,10,DARK,r=2)
        plate(r,wrist,'Titan forearm bright bevel '+label,[(-31,-10),(21,-17),(35,-3),(31,24),(17,18),(-19,24),(-32,15)],GOLD,4)
        plate(r,wrist,'Titan heavy forearm '+label,[(-34,-9),(22,-18),(39,-3),(36,48),(23,58),(-25,61),(-39,45)],IVORY,6)
        plate(r,wrist,'Titan forearm deep shell '+label,[(-39,-13),(25,-23),(45,-5),(42,52),(26,66),(-29,69),(-45,47)],DARK,7)
        upper=forward(arm,r.node(arm,'Titan upper arm machinery '+label))
        slider=r.node(upper,'Titan telescoping piston '+label,y=26)
        r.bind(slider,'y','titanPiston'+label,26)
        r.rect(slider,'Titan polished ram '+label,0,0,14,38,STEEL,r=3)
        r.rect(upper,'Titan piston socket '+label,0,10,28,27,DARK,r=6)
        cable(r,upper,'Titan arm service hose '+label,[(side*16,4),(side*24,19),(side*19,39)],GOLD,4)
        ring(r,upper,'Titan shoulder slew '+label,0,0,48,0 if side<0 else 1)
        # Two large plates fold into a mechanical bastion in the guard pose.
        pauldron=r.node(upper,'Titan shield shoulder '+label)
        r.bind(pauldron,'rotation','titanShieldWing'+label,0)
        for x,y in [(-23,-19),(24,-16)]:bolt(r,pauldron,f'Pauldron {label}-{x}',x,y,7)
        for i in range(3):
            cable(r,pauldron,f'Shield panel machining {label}-{i}',[(21+i*4,-29+i*3),(31+i*3,-19+i*3)],EDGE,1.2)
        glow(r,pauldron,'Titan shoulder running light '+label,0,-27,34,4)
        plate(r,pauldron,'Titan shield panel highlight '+label,[(-39,-29),(-19,-42),(30,-36),(45,-17),(21,-24),(-22,-27)],IVORY,3)
        plate(r,pauldron,'Titan angular shield pauldron '+label,[(-39,-29),(-19,-42),(30,-36),(45,-17),(37,13),(16,26),(-25,18),(-44,-1)],GOLD,5)
        plate(r,pauldron,'Titan pauldron dark depth '+label,[(-44,-33),(-21,-47),(34,-41),(51,-18),(43,17),(18,32),(-30,24),(-50,0)],DARK,6)
        fit_materials(arm)
        # Gauntlets cross in front of the pressure engine. The builder puts
        # the helmet above them afterwards, so a salute never covers the face.
        r.robot.remove(arm)
        r.robot.insert(0,arm)
