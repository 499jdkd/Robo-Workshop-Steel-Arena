"""Preservation, collection economies and shared strategic counters."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from armory import WEAPONS
from collection_progress import ensure,add_season_xp,refresh_season,roll_container
from combat_rules import fighter,resolve_action,allowed
from equipment_catalog import effective_stats
from gameplay import GameState,perform
from local_store import LocalStore
from robot_catalog import ROBOTS
from robot_designs import DESIGNS

NOW=1_800_000_000

class CollectionUpdateTests(unittest.TestCase):
    def state(self):return GameState(level=30,coin=100000,food=500,robot_levels={'spark':4,'titan':2},active_robot='spark',egg_id='')
    def test_old_save_has_immutable_archive_and_all_data_survives(self):
        legacy={'schema':2,'device_id':'existing','state':{'coin':1753,'food':85,'robot_levels':{'spark':5,'nova':3},'robot_xp':{'spark':42},'active_robot':'spark','weapon_levels':{'laser':4},'loadouts':{'spark':['laser']},'craft_counts':{'lamp':7},'username':'Инженер','accent':'#248E83'}}
        with tempfile.TemporaryDirectory() as folder:
            store=LocalStore(folder);store.save(legacy);state=GameState.from_dict(store.load()['state'])
            for key,value in legacy['state'].items():
                if key=='robot_xp':
                    for robot,xp in value.items():self.assertEqual(state.robot_xp[robot],xp)
                else:self.assertEqual(getattr(state,key),value,key)
            migrated={'schema':2,'state':state.to_dict(),'device_id':'existing'};store.save(migrated)
            archive=Path(folder)/'workshop-save-before-collection-v3.json'
            self.assertEqual(json.loads(archive.read_text(encoding='utf8')),legacy)
            content=archive.read_bytes();store.save(migrated);self.assertEqual(archive.read_bytes(),content)
            self.assertEqual(GameState.from_dict(store.load()['state']).to_dict(),state.to_dict())
    def test_all_constructions_weapons_and_item_art_exist(self):
        self.assertGreaterEqual(len(ROBOTS),30);self.assertEqual(len(DESIGNS),len({d['construction'] for d in DESIGNS.values()}))
        self.assertGreaterEqual(len(WEAPONS),20)
        for r in ROBOTS:self.assertTrue((ROOT/'src/assets'/r.image).exists())
        for w in WEAPONS:self.assertTrue((ROOT/'src/assets/art/weapons'/f'{w.id}.svg').exists())
    def test_fragment_unlock_stars_duplicate_action_and_restart(self):
        state=self.state();data=ensure(state);data['fragments']['arachna']=120
        self.assertTrue(perform(state,'fragment_unlock',['arachna'],NOW).ok)
        self.assertEqual(data['fragments']['arachna'],90)
        before=state.to_dict();self.assertFalse(perform(state,'fragment_unlock',['arachna'],NOW).ok);self.assertEqual(state.to_dict(),before)
        self.assertTrue(perform(state,'star_up',['arachna'],NOW).ok)
        restored=GameState.from_dict(state.to_dict());self.assertEqual(restored.collection['stars']['arachna'],2);self.assertEqual(restored.collection['fragments']['arachna'],70)
    def test_module_changes_real_battle_and_survives_restart(self):
        state=self.state();initial=effective_stats(state,'spark')
        self.assertTrue(perform(state,'module_buy',['alloy'],NOW).ok)
        self.assertTrue(perform(state,'module_equip',['alloy','spark'],NOW).ok)
        self.assertEqual(effective_stats(state,'spark')['health'],initial['health']+8)
        restored=GameState.from_dict(state.to_dict());self.assertEqual(restored.collection,state.collection)
        perform(state,'battle_start',['spark'],NOW)
        self.assertEqual(state.battle['player_max_hp'],effective_stats(state,'spark')['health'])
        self.assertFalse(perform(state,'module_remove',['alloy','spark'],NOW).ok)
    def test_season_claim_is_idempotent_and_respects_level_cap(self):
        state=self.state();add_season_xp(state,600,NOW)
        self.assertTrue(perform(state,'season_claim_all',[],NOW).ok)
        before=state.to_dict();self.assertFalse(perform(state,'season_claim_all',[],NOW).ok);self.assertEqual(before,state.to_dict())
        self.assertEqual(sorted(state.collection['season']['free']),[1,2,3])
        self.assertFalse(perform(state,'season_claim',[50,'free'],NOW).ok)
        self.assertFalse(perform(state,'season_claim',[1,'premium'],NOW).ok)
        self.assertEqual(GameState.from_dict(state.to_dict()).collection,state.collection)
    def test_factory_commits_before_animation_and_cannot_reopen_empty_inventory(self):
        state=self.state();data=ensure(state)
        self.assertEqual(data['chests']['normal'],1)
        self.assertTrue(perform(state,'factory_open',['normal',1],NOW).ok)
        self.assertTrue(data['factory_rewards']);self.assertTrue(data['factory_receipt'])
        saved=state.to_dict();self.assertFalse(perform(state,'factory_open',['normal',1],NOW).ok);self.assertEqual(saved,state.to_dict())
        self.assertFalse(perform(state,'factory_open',['parts',-5],NOW).ok)
        self.assertEqual(GameState.from_dict(saved).collection,state.collection)
    def test_daily_factory_and_xp_are_bounded(self):
        state=self.state();self.assertTrue(perform(state,'factory_daily',[],NOW).ok)
        self.assertFalse(perform(state,'factory_daily',[],NOW).ok)
        self.assertEqual(add_season_xp(state,5000,NOW),900)
        self.assertEqual(add_season_xp(state,200,NOW),0)
        self.assertEqual(add_season_xp(state,200,NOW+86400),200)
    def test_module_malformed_save_does_not_invent_items_or_break_old_data(self):
        state=GameState.from_dict({'coin':82,'robot_levels':{'spark':2},'collection':{'stars':[],'modules':{'alloy':-4,'unknown':7},'module_loadouts':{'spark':{'armor':'unknown'}},'team':[{},[],'spark'],'season':{'free':[True,{},3]}}})
        self.assertEqual(state.coin,82);self.assertEqual(state.collection['modules'],{});self.assertEqual(state.collection['team'],['spark'])

class CounterTests(unittest.TestCase):
    def test_shield_piercing_and_emp(self):
        normal=fighter('spark');shield=fighter('titan');shield['guard']=True
        n=resolve_action(normal,shield,'attack',seed=3)['damage']
        a=fighter('nova','laser');b=fighter('titan');b['guard']=True
        piercing=resolve_action(a,b,'pierce',seed=3)
        self.assertTrue(piercing['shield_broken']);self.assertGreater(piercing['damage'],n)
        a=fighter('chronos','emp');b=fighter('guardian');b['guard']=True
        self.assertTrue(resolve_action(a,b,'emp')['ok']);self.assertFalse(b['guard']);self.assertEqual(b['emp'],2)
    def test_quick_interrupt_and_burst_counter_dodge(self):
        a=fighter('spark');b=fighter('goliath');b['preparing']=True
        e=resolve_action(a,b,'quick');self.assertTrue(e['interrupted']);self.assertEqual(b['stun'],1)
        a=fighter('rocketeer','rocket');b=fighter('ninja');b['dodge']=True
        e=resolve_action(a,b,'burst');self.assertEqual(e['hits'],3);self.assertGreater(e['damage'],0)
        a=fighter('spark');b=fighter('ninja');b['dodge']=True
        self.assertEqual(resolve_action(a,b,'attack')['damage'],0)
    def test_invalid_attack_is_atomic_and_every_robot_has_working_super(self):
        a=fighter('spark');b=fighter('titan');old=(deepcopy(a),deepcopy(b))
        self.assertFalse(resolve_action(a,b,'ultimate')['ok']);self.assertEqual((a,b),old)
        for robot,d in DESIGNS.items():
            a=fighter(robot,d['weapon']);b=fighter('titan');a['super_charge']=100
            self.assertTrue(resolve_action(a,b,'ultimate')['ok'],robot);self.assertLess(a['super_charge'],100)

if __name__=='__main__':unittest.main()
