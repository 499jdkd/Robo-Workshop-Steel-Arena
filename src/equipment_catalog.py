"""Individual module slots; all upgrades are bought with earned game currency."""
from dataclasses import dataclass

SLOTS = {'armor':'Броня','core':'Ядро','drive':'Двигатель','defense':'Защитный модуль','gadget':'Гаджет'}

@dataclass(frozen=True)
class Module:
    id: str
    title: str
    slot: str
    rarity: str
    price: int
    attribute: str
    bonus: int
    description: str

MODULES = (
 Module('alloy','Сотовая броня','armor','common',180,'health',8,'Больше здоровья без потери скорости'),
 Module('ceramic','Керамическая броня','armor','rare',420,'defense',3,'Снижает урон каждого попадания'),
 Module('reactor','Плазменное ядро','core','rare',380,'energy',1,'Увеличивает ёмкость батареи'),
 Module('capacitor','Импульсное ядро','core','epic',800,'regen',1,'Ускоряет восстановление энергии'),
 Module('servo','Сервоприводы','drive','common',220,'speed',6,'Повышают скорость и точность ответов'),
 Module('gyroscope','Гиростабилизатор','drive','rare',480,'crit',1,'Помогает точному наведению'),
 Module('barrier','Барьерный эмиттер','defense','rare',360,'defense',2,'Поглощает часть входящего урона'),
 Module('insulator','Изолятор EMP','defense','epic',760,'health',6,'Уменьшает длительность отключения щита'),
 Module('scope','Дальномер','gadget','rare',420,'crit',2,'Увеличивает критический шанс'),
 Module('overdrive','Боевой процессор','gadget','legendary',1400,'attack',2,'Усиливает штатное и установленное оружие'),
)
MODULE_BY_ID={m.id:m for m in MODULES}

def module_cost(module, level):return module.price if not level else module.price*(level+1)

def effective_stats(state, identity):
    from robot_designs import base_stats
    data=state.collection
    stats=base_stats(identity,state.robot_levels.get(identity,1),data.get('stars',{}).get(identity,1))
    for item in data.get('module_loadouts',{}).get(identity,{}).values():
        module=MODULE_BY_ID.get(item)
        if module:
            stats[module.attribute]+=module.bonus*data.get('modules',{}).get(item,0)
    stats['energy']=min(18,stats['energy'])
    stats['regen']=min(6,stats['regen'])
    stats['crit']=min(35,stats['crit'])
    return stats
