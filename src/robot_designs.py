"""Art, chassis, combat roles and unique skills: stable IDs are save keys.

The eight original IDs are retained. Each construction has its own articulated
Rive artboard; palette is not used as a substitute for a different silhouette.
"""

CLASSES = {'tank': 'Танк', 'striker': 'Штурмовик', 'support': 'Поддержка', 'scout': 'Разведчик', 'special': 'Особый'}

# id, name, construction, locomotion, class, element, native weapon, ultimate,
# counter/utility, weakness, unlock level, rarity, color
ROWS = (
 ('spark','Искра','buggy','wheels','scout','steel','plasma','Двойная искра','Два импульса обходят уворот','Лёгкая броня',1,'common','#FFB83F'),
 ('volt','Вольт','tesla','hover','striker','pulse','electric','Цепная молния','Прерывает подготовку тяжёлого удара','Небольшой запас здоровья',3,'common','#36DFFF'),
 ('flora','Флора','bioreactor','legs','support','nature','repair','Биовосстановление','Лечение и очищение перегрева','Уязвима к пробитию',6,'rare','#69E7A5'),
 ('forge','Кузя','loader','tracks','support','steel','fist','Кузнечный пресс','Оглушение и усиление брони','Малая скорость',10,'epic','#FF9258'),
 ('nova','Нова','reactor','hover','striker','cosmic','ion','Коллапс плазмы','Пробивает защиту одиночным импульсом','Высокое энергопотребление',16,'legendary','#BB86FF'),
 ('glacier','Норд','crystal','hover','scout','pulse','cryo','Абсолютный ноль','Замедляет ответ и охлаждает себя','Слаб против серий',8,'rare','#A5EFFF'),
 ('aegis','Бастион','tank','tracks','tank','steel','rocket','Подвижная крепость','Броня и ответный залп','Уязвим к EMP',13,'epic','#FF6D68'),
 ('solar','Гелиос','sun','hover','special','cosmic','laser','Солнечная корона','Лечение и пробивающий луч','Уязвим во время фокуса',22,'mythic','#FFD55C'),
 ('titan','Титан','juggernaut','legs','tank','steel','machinegun','Титановая стена','Поглощает удар и усиливает контратаку','Медленно набирает энергию',8,'rare','#F2C765'),
 ('arachna','Арахна','spider','hexapod','scout','nature','disc','Электросеть','Шесть лап и серия ловушек','Слабая защита корпуса',9,'epic','#BC79FF'),
 ('phantom','Фантом','cloak','hover','scout','cosmic','sniper','Невидимый выстрел','Уворот и точный выстрел','Не выдерживает очередей',11,'epic','#8971EC'),
 ('falcon','Сокол','falcon','flight','scout','pulse','blaster','Пикирование','Поднимается над ближними атаками','Лёгкие крылья',7,'rare','#50BEFF'),
 ('cyclops','Циклоп','tripod','tripod','striker','steel','sniper','Точка уязвимости','Прицел и сокрушительное пробитие','Долгая подготовка',12,'epic','#EC786B'),
 ('medic','Медик','medic','hover','support','nature','repair','Ремонтный рой','Лечит и восстанавливает энергию','Невысокий прямой урон',5,'common','#61DFA8'),
 ('atlas','Атлас','gorilla','legs','tank','steel','fist','Сейсмический хлопок','Массивные руки разрушают щит','Боится дальней стрельбы',14,'epic','#FFAA4B'),
 ('cerberus','Цербер','hound','quadruped','striker','nature','flame','Тройной наскок','Серия прыжков мешает уклонению','Расходует много энергии',15,'legendary','#EF7A63'),
 ('cobra','Кобра','serpent','segments','scout','nature','laser','Кольцевой захват','Сегменты опутывают противника','Уязвимые соединения',12,'epic','#64D9A2'),
 ('phoenix','Феникс','phoenix','flight','striker','cosmic','flame','Огненное возрождение','Пламя и небольшой ремонт','Нагрев после атаки',21,'legendary','#FF9454'),
 ('driller','Бурильщик','driller','tracks','tank','steel','drill','Тектонический бур','Проходит через защитную стойку','Низкая дальность',9,'rare','#E9B45C'),
 ('ninja','Ниндзя','ninja','runner','scout','pulse','sword','Теневой разрез','Рывок и ответ после уворота','Небольшое здоровье',13,'epic','#8A9CEA'),
 ('specter','Спектр','hologram','hover','special','cosmic','blaster','Голографический рой','Копии отвлекают при одиночной атаке','Очереди распознают копии',18,'legendary','#D298FF'),
 ('magneto','Магнето','magnet','hover','special','pulse','magnetic','Полярный шторм','Нарушает подготовку и притягивает цель','Уязвим к ближнему бою',17,'epic','#FC718E'),
 ('rocketeer','Ракетчик','artillery','tracks','striker','steel','rocket','Ковровый залп','Несколько ракет против уклонения','Долгая перезарядка',15,'epic','#F2B24E'),
 ('octopus','Осьминог','octopus','tentacles','support','nature','drone','Восемь инструментов','Щупальца ремонтируют и атакуют','Слаб к импульсу EMP',19,'legendary','#9F93FF'),
 ('scarab','Скарабей','beetle','quadruped','tank','steel','grenade','Панцирь-рикошет','Бронированная оболочка и контратака','Уязвимые суставы',10,'rare','#D0B95D'),
 ('orbit','Орбита','gyro','hover','special','cosmic','ion','Орбитальная волна','Вращающиеся кольца усиливают импульс','Небольшая броня',20,'legendary','#6CE1FF'),
 ('guardian','Страж','guardian','legs','tank','pulse','shield','Эгида команды','Огромный щит и возврат энергии','EMP отключает щит',16,'epic','#76BFFF'),
 ('goliath','Голиаф','siege','quadruped','tank','steel','sniper','Осадный разряд','Тяжёлый залп разрушает броню','Быстрые атаки прерывают заряд',24,'legendary','#CC9A65'),
 ('chronos','Хронос','clock','hover','special','cosmic','emp','Временная петля','Замедляет действие и сбрасывает нагрев','Длительное восстановление',26,'mythic','#B6A5FF'),
 ('omega','Омега','transformer','hexapod','special','cosmic','plasma','Омега-конверсия','Трансформация меняет атаку и защиту','Нужна энергия для смены формы',30,'mythic','#FFE681'),
 ('storm','Шторм','storm','flight','striker','pulse','electric','Грозовой фронт','Разряды прерывают подготовку','Перегрев от серий',23,'legendary','#79D8FF'),
 ('chameleon','Хамелеон','gecko','quadruped','scout','nature','disc','Адаптивная броня','Меняет защиту после полученного урона','Уязвим к смене типа атаки',25,'legendary','#A8E776'),
)

DESIGNS = {r[0]: dict(zip(('id','name','construction','mobility','class','element','weapon','ultimate','strength','weakness','unlock','rarity','color'), r)) for r in ROWS}
RARITY_FRAGMENTS = {'common':10,'rare':20,'epic':30,'legendary':60,'mythic':80}
STAR_COSTS = (20,40,80,120)


def spec(identity):
    return DESIGNS.get(identity, DESIGNS['spark'])


def base_stats(identity, level=1, stars=1):
    d = spec(identity)
    role = d['class']
    health = {'tank':108,'striker':78,'support':86,'scout':70,'special':80}[role] + 14 * (level-1)
    attack = {'tank':11,'striker':15,'support':10,'scout':12,'special':13}[role] + 3 * (level-1)
    rank = 1 + .07 * (stars-1)
    return dict(health=round(health*rank), attack=round(attack*rank), defense={'tank':16,'support':9,'striker':6,'scout':4,'special':7}[role],
                speed={'tank':65,'striker':100,'support':90,'scout':130,'special':95}[role], crit=8 if role != 'scout' else 14,
                crit_damage=150, energy=12, regen=3, capacity=5 if role=='tank' else 4 if role in ('striker','special') else 3)
