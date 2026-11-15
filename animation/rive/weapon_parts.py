"""Reusable articulated weapon assemblies for each robot's right mount."""
def add_weapons(builder,fore):
    b=builder
    for kind in ('cryo','ion','blaster','magnetic','grenade','emp','drill','disc','repair'):
        gun=b.node(fore,kind+' assembly',y=18)
        b.bind(gun,'opacity',kind,0);b.bind(gun,'scaleY','deploy',.01)
        if kind=='cryo':
            for i in range(6):
                fin=b.node(gun,f'Cryo vane {i}',rotation=i*3.14159265/3,y=65)
                b.path(fin,f'Crystal edge {i}',[(0,10),(-9,-19),(0,-42),(9,-19)],('FFE6FFFF','FF6AB9DF'))
            b.rect(gun,'Cold bore',0,42,29,83,r=8)
        elif kind=='ion':
            b.oval(gun,'Ion sphere',0,92,43,43,('FFFFFFFF','FF9FEAFF','FF3588D5'))
            for x in (-28,28):b.rect(gun,f'Ion rail {x}',x,54,10,93,b.paint,r=4)
            b.plate(gun,'Ion receiver',0,24,50,55)
        elif kind=='blaster':
            for x in (-16,16):b.rect(gun,f'Pulse barrel {x}',x,65,18,87,r=6)
            b.plate(gun,'Pulse housing',0,28,55,55)
        elif kind=='magnetic':
            b.path(gun,'Magnetic yoke',[(-25,100),(-25,32),(25,32),(25,100)],('FFEDFAFF','FF8096B4'),stroke=18)
            for x in (-25,25):b.rect(gun,f'Magnetic pole {x}',x,100,24,20,('FFFFBCD0','FFDA4977'),r=4)
        elif kind=='grenade':
            import math
            b.oval(gun,'Grenade drum',0,42,68,68,('FF4C6283','FF13243D'))
            for i in range(5):b.oval(gun,f'Drum chamber {i}',math.cos(i*math.tau/5)*22,42+math.sin(i*math.tau/5)*22,13,13,b.paint)
            b.rect(gun,'Grenade short barrel',0,83,34,40,r=8)
        elif kind=='emp':
            for y in (40,62,84):b.oval(gun,f'EMP ring {y}',0,y,56,12,('FFE2FFFF','FF63C9EE'))
            b.rect(gun,'EMP emitter mast',0,54,18,90,r=7)
        elif kind=='drill':
            rotor=b.node(gun,'Mechanical bore',y=47);b.bind(rotor,'rotation','gunRotor',0)
            b.path(rotor,'Bore cone',[(-31,-12),(0,74),(31,-12)])
            for y in (0,18,36):b.path(rotor,f'Bore helix {y}',[(-25+y/3,y),(22-y/3,y+15)],b.paint,stroke=7)
            b.plate(gun,'Bore chuck',0,14,60,38)
        elif kind=='disc':
            for y in (28,50,72):b.oval(gun,f'Disc magazine {y}',0,y,63,15)
            b.rect(gun,'Disc accelerator',0,93,51,13,b.paint,r=5)
        else:
            b.rect(gun,'Repair core',0,53,40,91,('FFDDFFEC','FF2DAF84'),r=12)
            b.rect(gun,'Repair cross upright',0,55,9,36,'FFEEFFF8',r=2)
            b.rect(gun,'Repair cross horizontal',0,55,28,9,'FFEEFFF8',r=2)
