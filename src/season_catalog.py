"""Global 30-day season schedule and its 50 deterministic reward levels."""
SEASON_SECONDS=30*86400
LEVEL_XP=200
LEVELS=50
DAILY_XP_CAP=900

def season_at(now):
    period=int(max(0,now)//SEASON_SECONDS)
    return {'id':period,'name':'Стальной рассвет','start':period*SEASON_SECONDS,'end':(period+1)*SEASON_SECONDS}

def reward_at(level,premium=False):
    if level==50:return {'kind':'fragments','id':'omega','amount':10 if premium else 20,'rarity':'mythic'}
    cycle=(
      {'kind':'gold','amount':100+level*10,'rarity':'common'},
      {'kind':'parts','amount':4+level//5,'rarity':'common'},
      {'kind':'chests','id':'rare' if level%10==3 else 'normal','amount':1,'rarity':'rare'},
      {'kind':'fragments','id':('titan','arachna','medic','falcon','orbit')[level//5%5],'amount':5,'rarity':'epic'},
      {'kind':'crystals','amount':10,'rarity':'epic'},
      {'kind':'food','amount':20+level,'rarity':'common'},
      {'kind':'blueprints','id':('ion','cryo','emp','disc')[level//7%4],'amount':3,'rarity':'rare'},
      {'kind':'cores','amount':1,'rarity':'epic'},
      {'kind':'module','id':('alloy','servo','scope','barrier')[level//9%4],'amount':1,'rarity':'rare'},
      {'kind':'skin','id':f'steel-{min(5,level//10)}','amount':1,'rarity':'legendary'},
    )
    reward=dict(cycle[(level-1)%10])
    if premium:
        # Cosmetics and convenience; normalized ranked stats never read this.
        reward={'kind':'emblem' if level%2 else 'animation','id':f'season-{level}','amount':1,'rarity':'epic'} if level%5==0 else dict(reward)
    return reward
