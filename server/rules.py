"""Server access to the same pure, versioned catalogs/resolver as offline play.

No client save, levels, damage or currency is accepted by this boundary.
"""
import sys
from pathlib import Path

SOURCE = str(Path(__file__).resolve().parents[1] / 'src')
if SOURCE not in sys.path:
    sys.path.insert(0, SOURCE)

from armory import BY_ID
from combat_rules import ACTIONS, action_error, fighter, resolve_action
from robot_designs import DESIGNS

ROBOTS=set(DESIGNS)
WEAPONS={key:(value.damage,value.energy) for key,value in BY_ID.items()}


def arena_actor(robot,weapon):
    """Equal HP/damage budgets, with bounded class identity and speed tradeoffs."""
    role=DESIGNS[robot]['class']
    health,attack,defense,speed={
        'tank':(150,16,10,75),'striker':(125,21,5,100),
        'support':(135,17,7,95),'scout':(115,19,5,125),
        'special':(125,19,7,100),
    }[role]
    return fighter(robot,weapon,health=health,attack=attack,defense=defense,speed=speed)


def combat_power(robot,weapon):
    actor=arena_actor(robot,weapon)
    return actor['max_hp']+actor['attack']*8+actor['defense']*5+actor['speed']//3+BY_ID[weapon].damage


def league(rating):
    tiers=('Бронза','Серебро','Золото','Платина','Алмаз','Мастер')
    index=min(5,max(0,(rating-800)//300))
    return {'name':tiers[index],'division':min(3,max(1,(rating-800-index*300)//100+1))}
