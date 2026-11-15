"""Factory, season and earned-currency shop, integrated with the main router."""
import flet as ft

from armory import BY_ID,WEAPONS
from collection_progress import CHESTS,ODDS,RARITY_ORDER,ensure,refresh_season,reward_title
from equipment_catalog import MODULES
from game_countdown import GameCountdown
from game_ui import game_button,resource_hud,section_title,tabs
from progression_ui import stored_eggs_panel
from rewarded_ads import RewardPanel
from robot_catalog import RARITIES,ROBOT_BY_ID,ROBOTS
from season_catalog import LEVEL_XP,LEVELS,reward_at,season_at
from ui_shared import GOLD,GREEN,INK,MUTED,card,notice,tint,use_game

@ft.control('GameFactory')
class GameFactory(ft.Container):
    receipt: str = ''
    opened: bool = False

def navigate(session,destination):
    def go(_):session.route=destination;session.notify()
    return go

def reward_icon(reward):
    kind=reward['kind'];identity=reward.get('id','')
    if kind=='fragments' and identity in ROBOT_BY_ID:return ROBOT_BY_ID[identity].image
    if kind=='blueprints' and identity in BY_ID:return f'art/weapons/{identity}.svg'
    if kind=='module':return f'art/modules/{identity}.svg'
    return {'gold':'art/icons/credits.svg','food':'art/icons/food.svg','crystals':'art/icons/crystal.svg','chests':'art/icons/container.svg','cores':'art/modules/reactor.svg','parts':'art/icons/parts.svg','rare_parts':'art/icons/parts.svg','skin':'art/icons/profile.svg','emblem':'art/icons/arena.svg','animation':'art/icons/profile.svg'}.get(kind,'art/icons/parts.svg')

def reward_card(reward,*,status='',premium=False):
    color=RARITIES.get(reward.get('rarity','common'),RARITIES['common'])[1]
    return ft.Container(ft.Row([ft.Image(reward_icon(reward),width=38,height=42,fit=ft.BoxFit.CONTAIN),ft.Column([ft.Text(reward_title(reward),color=INK,size=10,weight=ft.FontWeight.BOLD,max_lines=3),ft.Text(status,color=GREEN if status=='Получено' else GOLD if status=='Доступно' else MUTED,size=9)],expand=True,spacing=3)],spacing=6),
       padding=7,border_radius=10,border=ft.Border.all(1,color),gradient=ft.LinearGradient(colors=[tint(color,.2),'#162844']),expand=True)

@ft.component
def FeatureScreen(page,session):
    use_game(session)
    screen=session.route
    titles={'season':'Стальной сезон','factory':'Робофабрика','store':'Магазин'}
    header=ft.Row([ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED,on_click=navigate(session,''),icon_color='#8CE2FF',key='feature-back'),ft.Text(titles.get(screen,'Мастерская'),color=INK,size=22,weight=ft.FontWeight.BOLD,expand=True)],spacing=6)
    body=SeasonScreen(page=page,session=session) if screen=='season' else FactoryScreen(page=page,session=session) if screen=='factory' else StoreScreen(page=page,session=session)
    return ft.Column([header,body],expand=True,spacing=8)

@ft.component
def SeasonScreen(page,session):
    state=use_game(session);data=ensure(state);now=session.clock();season=refresh_season(state,now);config=season_at(now)
    level=min(LEVELS,season['xp']//LEVEL_XP);available=sum(n not in season['free'] for n in range(1,level+1))
    def command(name,*args):
        def run(_):session.act(name,*args)
        return run
    rows=[resource_hud(state),card(ft.Column([
        ft.Row([ft.Image('art/icons/arena.svg',width=57,height=57),ft.Column([ft.Text('STEEL SEASON',color=GOLD,size=23,weight=ft.FontWeight.BOLD),ft.Text(config['name'],color=INK,size=12)],spacing=3,expand=True)],spacing=10),
        ft.Text('Сражайся, изобретай и развивай команду. Награды доступны за игру.',color=MUTED,size=11),
        ft.Text(f'Уровень сезона {level} / {LEVELS} · Опыт {season["xp"]} / {LEVEL_XP*LEVELS}',color=INK,size=12,weight=ft.FontWeight.BOLD),
        ft.ProgressBar(value=1 if level==LEVELS else (season['xp']%LEVEL_XP)/LEVEL_XP,color='#D78AFF',bgcolor='#293657',height=12,border_radius=6),
        ft.Text(f'До завершения: {max(0,int((config["end"]-now)//86400))} дн. {max(0,int((config["end"]-now)//3600)%24)} ч.',color='#93DBFF',size=11),
        game_button(f'Забрать всё · {available}',command('season_claim_all'),key='season-claim-all',disabled=not available),
    ],spacing=10),gradient=ft.LinearGradient(colors=['#294B84','#2A2257'])),
      card(ft.Text('Бесплатная линия приносит ресурсы и фрагменты. Премиум пока закрыт: подключение платежей не завершено. Нормализованный PvP не учитывает сезонные бонусы.',color=MUTED,size=11)),
      ft.Row([ft.Text('БЕСПЛАТНО',color='#81DAFF',weight=ft.FontWeight.BOLD,expand=True,text_align=ft.TextAlign.CENTER),ft.Text('Ур.',color=GOLD,size=11),ft.Text('ПРЕМИУМ 🔒',color=GOLD,weight=ft.FontWeight.BOLD,expand=True,text_align=ft.TextAlign.CENTER)],spacing=6)]
    for n in range(1,LEVELS+1):
        claimed=n in season['free'];ready=n<=level and not claimed
        free=reward_card(reward_at(n),status='Получено' if claimed else 'Доступно' if ready else f'{n*LEVEL_XP} XP')
        free.on_click=command('season_claim',n,'free') if ready else None
        paid=reward_card(reward_at(n,True),status='Премиум закрыт',premium=True)
        rows.append(ft.Row([free,ft.Container(ft.Text(str(n),color=GOLD,size=14,weight=ft.FontWeight.BOLD),width=22,alignment=ft.Alignment.CENTER),paid],spacing=5))
    from progression_ui import daily_panel
    from armory_ui import weekly_panel
    rows.extend([section_title('Задания сезона'),daily_panel(session),weekly_panel(session),notice(session)])
    return ft.Column(rows,spacing=8,scroll=ft.ScrollMode.AUTO,expand=True)

@ft.component
def FactoryScreen(page,session):
    state=use_game(session);data=ensure(state);kind,set_kind=ft.use_state('normal')
    def command(name,*args):
        def run(_):session.act(name,*args)
        return run
    chest=CHESTS[kind];count=data['chests'].get(kind,0)
    rows=[resource_hud(state),card(ft.Column([
        section_title(chest[0],f'В хранилище: {count}'),
        GameFactory(receipt=data['factory_receipt'],opened=bool(data['factory_receipt']),height=230,key='factory-opening'),
        ft.Row([game_button('Открыть',command('factory_open',kind,1),key='factory-open',disabled=count<1,expand=True),game_button('Открыть ×5',command('factory_open',kind,5),kind='blue',key='factory-open-five',disabled=count<5,expand=True)],spacing=8),
        game_button(f'Купить · {chest[1]} золота',command('factory_buy',kind,1),kind='green',disabled=state.coin<chest[1]),
      ],spacing=10),padding=12),
      tabs([v[0].replace('Контейнер ','').replace(' контейнер','') for v in CHESTS.values()],list(CHESTS).index(kind),lambda i:set_kind(list(CHESTS)[i])),
      game_button('Бесплатный контейнер дня',command('factory_daily'),kind='purple',key='factory-daily',disabled=int(session.clock()//86400)<=data['factory_day']),
      notice(session)]
    if data['factory_rewards']:
        rows.append(section_title('Полученные предметы','Награды уже записаны в сохранение'))
        for reward in data['factory_rewards']:rows.append(reward_card(reward))
    weights=ODDS.get(kind)
    if weights:
        rows.append(card(ft.Column([ft.Text('Вероятности редкости',color=INK,weight=ft.FontWeight.BOLD,size=13),ft.Text(' · '.join(f'{RARITIES[r][0]} {w/100:g}%' for r,w in zip(RARITY_ORDER,weights)),color=MUTED,size=11),ft.Text('Гарантированный путь: фрагменты за победы, задания и прямую покупку за заработанное золото. Контейнеры не продаются за реальные деньги.',color=MUTED,size=11)],spacing=7)))
    else:rows.append(card(ft.Text('Оружейный контейнер: 3–6 чертежей одного из 20 видов оружия, каждый с вероятностью 5%, и 40 золота. Ящик деталей: 6–12 деталей равновероятно и 1 ядро.',color=MUTED,size=11)))
    rows.extend([stored_eggs_panel(session),RewardPanel(page=page,session=session)])
    return ft.Column(rows,spacing=10,scroll=ft.ScrollMode.AUTO,expand=True)

@ft.component
def StoreScreen(page,session):
    state=use_game(session);data=ensure(state);tab,set_tab=ft.use_state(0)
    def command(name,*args):
        def run(_):session.act(name,*args)
        return run
    rows=[resource_hud(state),tabs(['Роботы','Оружие','Модули','Контейнеры','Внешний вид','Предложения'],tab,set_tab),notice(session)]
    if tab in {0,5}:
        robots=list(ROBOTS) if tab==0 else [ROBOTS[int(session.clock()//86400)%len(ROBOTS)],ROBOTS[(int(session.clock()//86400)+7)%len(ROBOTS)]]
        if tab==5:rows.append(card(ft.Text('Предложения дня обновляются в 00:00 UTC. Стоимость видна заранее, случайной покупки нет.',color=MUTED,size=11)))
        for robot in robots:
            price=30+DESIGN_UNLOCK(robot.id)*5
            def details(_,identity=robot.id):session.route='';session.robot_detail=identity;session.notify()
            rows.append(card(ft.Column([ft.Row([ft.Image(robot.image,width=67,height=80),ft.Column([ft.Text(robot.name,color=INK,size=15,weight=ft.FontWeight.BOLD),ft.Text(RARITIES[robot.rarity][0]+f' · Фрагменты {data["fragments"].get(robot.id,0)}',color=RARITIES[robot.rarity][1],size=11),ft.Text(robot.story,color=MUTED,size=10)],expand=True,spacing=4)],spacing=8),
             ft.Row([game_button(f'1 фрагмент · {price}',command('fragment_buy',robot.id),kind='green',disabled=state.coin<price,expand=True),game_button('Профиль',details,kind='blue',expand=True)],spacing=7)],spacing=8),padding=12))
    elif tab==1:
        from armory_ui import armory_panel
        rows.extend(armory_panel(session))
    elif tab==2:
        from equipment_catalog import module_cost
        for module in MODULES:
            level=data['modules'].get(module.id,0);price=module_cost(module,level)
            rows.append(card(ft.Column([ft.Row([ft.Image(f'art/modules/{module.id}.svg',width=50,height=50),ft.Column([ft.Text(module.title,color=INK,size=14,weight=ft.FontWeight.BOLD),ft.Text(module.description,color=MUTED,size=11)],expand=True)],spacing=9),game_button(f'{"Улучшить" if level else "Купить"} · {price}',command('module_upgrade' if level else 'module_buy',module.id),kind='green',disabled=level>=10 or state.coin<price)],spacing=9)))
    elif tab==3:
        for identity,(title,price) in CHESTS.items():
            rows.append(card(ft.Column([ft.Row([ft.Image('art/icons/container.svg',width=56,height=56),ft.Column([ft.Text(title,color=INK,size=14,weight=ft.FontWeight.BOLD),ft.Text('В инвентаре: '+str(data['chests'].get(identity,0)),color=MUTED,size=11)],expand=True)],spacing=8),ft.Row([game_button(f'Купить · {price}',command('factory_buy',identity),disabled=state.coin<price,expand=True),game_button('Робофабрика',navigate(session,'factory'),kind='blue',expand=True)],spacing=8)],spacing=8)))
    else:
        rows.append(card(ft.Column([section_title('Облики и эмоции'),ft.Text('Доступны в бесплатной линии сезона и за достижения. Перейди в профиль робота → «Внешний вид», чтобы применить открытую окраску.',color=MUTED,size=12),game_button('Открыть сезон',navigate(session,'season'))],spacing=10)))
        for skin in data['skins']:rows.append(card(ft.Text('Открыто: '+skin,color=GOLD,size=13)))
    return ft.Column(rows,spacing=10,scroll=ft.ScrollMode.AUTO,expand=True)

def DESIGN_UNLOCK(identity):
    from robot_designs import DESIGNS
    return DESIGNS[identity]['unlock']
