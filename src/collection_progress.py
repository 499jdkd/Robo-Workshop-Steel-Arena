"""Save-safe collection, modules, factory and seasonal progression rules."""
from copy import deepcopy
import random

from equipment_catalog import MODULE_BY_ID, SLOTS, module_cost
from robot_designs import DESIGNS, RARITY_FRAGMENTS, STAR_COSTS
from season_catalog import DAILY_XP_CAP, LEVEL_XP, LEVELS, reward_at, season_at

LIMIT=9_000_000_000_000_000
CHESTS={'normal':('Контейнер роботов',150), 'rare':('Редкий контейнер',450),
        'weapon':('Оружейный контейнер',240),'parts':('Ящик деталей',120),'capsule':('Капсула фрагментов',320)}
ODDS={'normal':(6500,2500,800,180,20),'rare':(3500,4000,2000,450,50),'capsule':(4000,3500,2000,450,50)}
RARITY_ORDER=('common','rare','epic','legendary','mythic')

def integer(value,maximum=LIMIT):
    return min(maximum,max(0,value)) if isinstance(value,int) and not isinstance(value,bool) else 0

def clean_map(raw,ids,maximum):
    return {key:integer(value,maximum) for key,value in raw.items() if key in ids and integer(value,maximum)} if isinstance(raw,dict) else {}

def restore(state,raw):
    from armory import BY_ID
    raw=raw if isinstance(raw,dict) else {}
    data={'version':3,'crystals':integer(raw.get('crystals')),'cores':integer(raw.get('cores')),
          'fragments':clean_map(raw.get('fragments'),DESIGNS,100000),
          'stars':{r:max(1,integer(raw.get('stars',{}).get(r),5)) for r in state.robot_levels} if isinstance(raw.get('stars',{}),dict) else {r:1 for r in state.robot_levels},
          'skills':clean_map(raw.get('skills'),state.robot_levels,5),
          'modules':clean_map(raw.get('modules'),MODULE_BY_ID,10),
          'module_loadouts':{},'blueprints':clean_map(raw.get('blueprints'),BY_ID,100000),
          'chests':clean_map(raw.get('chests'),CHESTS,10000),
          'factory_day':integer(raw.get('factory_day')),'factory_serial':integer(raw.get('factory_serial')),
          'factory_rewards':[],'factory_receipt':str(raw.get('factory_receipt',''))[:60],
          'season':{},'skins':[],'emblems':[],'animations':[],'skin_loadouts':{},'team':[]}
    if not raw: data['chests']={'normal':1}
    loadouts=raw.get('module_loadouts',{})
    if isinstance(loadouts,dict):
        for robot,items in loadouts.items():
            if robot not in state.robot_levels or not isinstance(items,dict):continue
            data['module_loadouts'][robot]={slot:item for slot,item in items.items() if slot in SLOTS and isinstance(item,str) and item in data['modules'] and MODULE_BY_ID[item].slot==slot}
    for name in ('skins','emblems','animations'):
        values=raw.get(name,[])
        data[name]=list(dict.fromkeys(v[:60] for v in values if isinstance(v,str)))[:256] if isinstance(values,list) else []
    if isinstance(raw.get('skin_loadouts'),dict):
        data['skin_loadouts']={r:v for r,v in raw['skin_loadouts'].items() if r in state.robot_levels and v in data['skins']}
    team=raw.get('team',[])
    if isinstance(team,list): data['team']=list(dict.fromkeys(r for r in team if isinstance(r,str) and r in state.robot_levels))[:3]
    season=raw.get('season',{})
    if isinstance(season,dict):
        data['season']={k:integer(season.get(k),maxval) for k,maxval in [('id',100000),('xp',LEVEL_XP*LEVELS),('day',10000000),('daily_xp',DAILY_XP_CAP)]}
        for key in ('free','premium'):
            values=season.get(key,[])
            data['season'][key]=list(dict.fromkeys(integer(v,LEVELS) for v in values if integer(v,LEVELS)))[:LEVELS] if isinstance(values,list) else []
    raw_rewards=raw.get('factory_rewards',[])
    if isinstance(raw_rewards,list):
        for item in raw_rewards[:25]:
            if isinstance(item,dict) and item.get('kind') in {'gold','food','parts','rare_parts','fragments','blueprints','cores','chests','module'}:
                data['factory_rewards'].append({k:v for k,v in item.items() if k in {'kind','id','amount','rarity'}})
    state.collection=data
    return data

def ensure(state):
    if state.collection.get('version')!=3:restore(state,state.collection)
    return state.collection

def refresh_season(state,now):
    data=ensure(state); current=season_at(now); season=data.get('season',{})
    if season.get('id')!=current['id'] or 'free' not in season:
        data['season']={'id':current['id'],'xp':0,'day':int(now//86400),'daily_xp':0,'free':[],'premium':[]}
    return data['season']

def add_season_xp(state,amount,now):
    season=refresh_season(state,now);day=int(now//86400)
    if day>season.get('day',0):season.update(day=day,daily_xp=0)
    gained=min(max(0,amount),DAILY_XP_CAP-season.get('daily_xp',0),LEVELS*LEVEL_XP-season['xp'])
    season['xp']+=gained;season['daily_xp']=season.get('daily_xp',0)+gained
    return gained

def grant(state,reward):
    data=ensure(state);kind=reward['kind'];amount=integer(reward.get('amount',1),1000000);identity=reward.get('id','')
    if kind=='gold':state.earn(amount,0)
    elif kind in {'food','parts','rare_parts'}:setattr(state,kind,min(LIMIT,getattr(state,kind)+amount))
    elif kind in {'crystals','cores'}:data[kind]=min(LIMIT,data.get(kind,0)+amount)
    elif kind in {'fragments','blueprints','chests'}:
        allowed=DESIGNS if kind=='fragments' else CHESTS if kind=='chests' else __import__('armory').BY_ID
        if identity in allowed:data[kind][identity]=min(100000,data[kind].get(identity,0)+amount)
    elif kind=='module' and identity in MODULE_BY_ID:
        if identity in data['modules']:data['cores']+=amount
        else:data['modules'][identity]=1
    elif kind in {'skin','emblem','animation'}:
        key={'skin':'skins','emblem':'emblems','animation':'animations'}[kind]
        if identity not in data[key]:data[key].append(identity)

def reward_title(reward):
    from armory import BY_ID
    names={'gold':'золота','food':'корма','parts':'деталей','rare_parts':'редких деталей','crystals':'кристаллов','cores':'ядер',
           'skin':'окраска','emblem':'эмблема','animation':'эмоция','chests':'контейнер','module':'модуль'}
    kind=reward['kind'];identity=reward.get('id','')
    title=DESIGNS.get(identity,{}).get('name','') if kind=='fragments' else BY_ID[identity].title if kind=='blueprints' and identity in BY_ID else MODULE_BY_ID[identity].title if kind=='module' and identity in MODULE_BY_ID else names.get(kind,kind)
    return f"{reward.get('amount',1)} {('фрагм. ' if kind=='fragments' else 'черт. ' if kind=='blueprints' else '')}{title}"

def roll_container(kind,serial):
    from armory import WEAPONS
    rng=random.Random(f'robo-factory-v3:{kind}:{serial}')
    if kind=='parts':return [{'kind':'parts','amount':rng.randint(6,12),'rarity':'common'},{'kind':'cores','amount':1,'rarity':'rare'}]
    if kind=='weapon':
        item=rng.choice(WEAPONS)
        return [{'kind':'blueprints','id':item.id,'amount':rng.randint(3,6),'rarity':item.rarity},{'kind':'gold','amount':40,'rarity':'common'}]
    rarity=rng.choices(RARITY_ORDER,weights=ODDS[kind])[0]
    if serial%10==0 and rarity=='common':rarity='rare'
    choices=[r for r in DESIGNS.values() if r['rarity']==rarity]
    item=rng.choice(choices)
    return [{'kind':'fragments','id':item['id'],'amount':rng.randint(3,6) if kind!='capsule' else 8,'rarity':rarity},
            {'kind':'gold','amount':rng.randint(30,60),'rarity':'common'}, {'kind':'food','amount':5,'rarity':'common'}]

def perform_collection(state,name,args,now):
    from gameplay import ActionResult
    actions={'fragment_unlock','star_up','skill_up','team_toggle','module_buy','module_upgrade','module_equip','module_remove',
             'factory_buy','factory_open','factory_daily','season_claim','season_claim_all','blueprint_craft','skin_equip','fragment_buy'}
    if name not in actions:return None
    data=ensure(state);identity=args[0] if args else '';battle=state.battle.get('result')=='active'
    def result(ok,message):
        if ok:state.modified_at=now
        return ActionResult(ok,message)
    if name.startswith('module_'):
        module=MODULE_BY_ID.get(identity)
        if not module:return result(False,'Модуль не найден')
        level=data['modules'].get(identity,0)
        if name in {'module_equip','module_remove'}:
            robot=args[1] if len(args)>1 else state.active_robot
            if battle or robot not in state.robot_levels:return result(False,'Меняй экипировку между боями')
            slots=data['module_loadouts'].setdefault(robot,{})
            if name=='module_remove':slots.pop(module.slot,None);return result(True,'Модуль снят')
            if not level:return result(False,'Сначала получи модуль')
            slots[module.slot]=identity;return result(True,f'Установлено: {module.title}')
        if (name=='module_buy' and level) or (name=='module_upgrade' and (not level or level>=10)):return result(False,'Проверь уровень модуля')
        price=module_cost(module,level);cores=1 if level>=3 else 0
        if state.coin<price or data['cores']<cores:return result(False,f'Нужно {price} золота и {cores} ядер')
        state.coin-=price;data['cores']-=cores;data['modules'][identity]=level+1
        add_season_xp(state,12,now);return result(True,f'{module.title}: уровень {level+1}')
    if name in {'fragment_unlock','star_up','skill_up','fragment_buy','team_toggle'}:
        robot=DESIGNS.get(identity)
        if not robot:return result(False,'Робот не найден')
        owned=identity in state.robot_levels
        if name=='fragment_buy':
            price=30+robot['unlock']*5
            if state.coin<price:return result(False,f'Нужно {price} золота за 1 фрагмент')
            state.coin-=price;data['fragments'][identity]=data['fragments'].get(identity,0)+1
            return result(True,'Получен гарантированный фрагмент')
        if name=='team_toggle':
            if not owned:return result(False,'Сначала открой робота')
            team=data['team']
            if identity in team:team.remove(identity)
            elif len(team)<3:team.append(identity)
            else:return result(False,'В отряде три места. Убери одного робота')
            return result(True,'Отряд обновлён')
        if battle:return result(False,'Заверши бой перед улучшением')
        if name=='fragment_unlock':
            cost=RARITY_FRAGMENTS[robot['rarity']]
            if owned or data['fragments'].get(identity,0)<cost:return result(False,f'Для открытия нужно {cost} фрагментов')
            data['fragments'][identity]-=cost;state.robot_levels[identity]=1;state.robot_energy[identity]=70;state.robot_xp[identity]=0;data['stars'][identity]=1
            if not state.active_robot:state.active_robot=identity
            if state.egg_id==identity:state.egg_id='';state.egg_ready_at=state.egg_started_at=0
            add_season_xp(state,40,now);return result(True,f'{robot["name"]} присоединился!')
        if not owned:return result(False,'Сначала открой робота')
        if name=='star_up':
            rank=data['stars'].get(identity,1)
            if rank>=5:return result(False,'Максимум 5 звёзд')
            cost=STAR_COSTS[rank-1]
            if data['fragments'].get(identity,0)<cost:return result(False,f'Нужно {cost} фрагментов')
            data['fragments'][identity]-=cost;data['stars'][identity]=rank+1
            add_season_xp(state,30,now);return result(True,f'{robot["name"]}: {rank+1} звезды')
        level=data['skills'].get(identity,1);price=250*level;cores=max(0,level-1)
        if level>=5 or state.coin<price or data['cores']<cores:return result(False,f'Нужно {price} золота и {cores} ядер; максимум 5 уровней')
        state.coin-=price;data['cores']-=cores;data['skills'][identity]=level+1
        return result(True,f'Суперспособность: уровень {level+1}')
    if name=='factory_daily':
        day=int(now//86400)
        if day<=data['factory_day']:return result(False,'Бесплатный контейнер уже получен')
        data['factory_day']=day;data['chests']['normal']=data['chests'].get('normal',0)+1
        return result(True,'Ежедневный контейнер получен')
    if name in {'factory_buy','factory_open'}:
        if identity not in CHESTS:return result(False,'Контейнер не найден')
        count=args[1] if len(args)>1 and isinstance(args[1],int) and not isinstance(args[1],bool) else 1
        if count not in {1,5}:return result(False,'Можно открыть 1 или 5 контейнеров')
        if name=='factory_buy':
            price=CHESTS[identity][1]*count
            if state.coin<price:return result(False,f'Нужно {price} золота')
            state.coin-=price;data['chests'][identity]=data['chests'].get(identity,0)+count
            return result(True,'Контейнеры отправлены на фабрику')
        if data['chests'].get(identity,0)<count:return result(False,'Недостаточно контейнеров')
        rewards=[];data['chests'][identity]-=count
        for _ in range(count):
            data['factory_serial']+=1;rewards.extend(roll_container(identity,data['factory_serial']))
        for reward in rewards:grant(state,reward)
        data['factory_rewards']=rewards;data['factory_receipt']=f"factory:{data['factory_serial']}:{now:.3f}"
        state.crates_opened+=count;add_season_xp(state,5*count,now)
        return result(True,'Контейнер открыт. Все награды сохранены')
    if name in {'season_claim','season_claim_all'}:
        season=refresh_season(state,now);available=min(LEVELS,season['xp']//LEVEL_XP)
        line=args[1] if len(args)>1 else 'free'
        if line!='free':return result(False,'Премиум требует подтверждённой покупки; платежи ещё не подключены')
        levels=[identity] if name=='season_claim' and isinstance(identity,int) else list(range(1,available+1)) if name=='season_claim_all' else []
        levels=[n for n in levels if 1<=n<=available and n not in season['free']]
        if not levels:return result(False,'Доступных наград пока нет')
        for n in levels:season['free'].append(n);grant(state,reward_at(n))
        return result(True,f'Получено наград сезона: {len(levels)}')
    if name=='blueprint_craft':
        from armory import BY_ID
        weapon=BY_ID.get(identity)
        if not weapon or identity in state.weapon_levels or data['blueprints'].get(identity,0)<10:return result(False,'Нужно 10 чертежей нового оружия')
        data['blueprints'][identity]-=10;state.weapon_levels[identity]=1
        return result(True,f'Создано: {weapon.title}')
    if name=='skin_equip':
        robot=args[1] if len(args)>1 else state.active_robot
        if robot not in state.robot_levels or identity not in data['skins']:return result(False,'Окраска ещё не открыта')
        data['skin_loadouts'][robot]=identity;return result(True,'Окраска установлена')
    return result(False,'Действие недоступно')

def record_activity(state,name,before,now):
    data=ensure(state)
    # Derive XP from committed changes, never from button presses or animation.
    amount=(state.arena_wins-before['wins'])*40+(state.jobs_done-before['jobs'])*30+(state.robot_trainings-before['training'])*20
    amount+=max(0,state.manual_taps//20-before['taps']//20)
    if name=='feed':amount+=2
    if name in {'daily','weekly_claim','goal'}:amount+=20
    if amount:add_season_xp(state,amount,now)
    if state.arena_wins>before['wins']:
        identity=list(DESIGNS)[(state.arena_wins-1)%len(DESIGNS)]
        grant(state,{'kind':'fragments','id':identity,'amount':2})
    for robot in state.robot_levels:data['stars'].setdefault(robot,1)
