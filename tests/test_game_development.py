"""Save migration, equipment economies and real two-client server invariants."""

import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

from armory import WEEKLY, refresh_week
from gameplay import GameState, perform
from robot_arena import restore_battle, take_turn
from server.arena_service import ArenaService, RuleError


class EquipmentTests(unittest.TestCase):
    def test_malformed_new_save_fields_do_not_break_existing_progress(self):
        state=GameState.from_dict({'coin':123,'robot_levels':{'spark':2},'active_robot':'spark','weapon_levels':{'laser':3},'loadouts':{'spark':[{},[],True,'laser']},'weekly':{'claimed':[[],{},'taps']},'arena_difficulty':[]})
        self.assertEqual(state.coin,123)
        self.assertEqual(state.loadouts,{'spark':['laser']})
        self.assertEqual(state.arena_difficulty,'normal')
    def state(self):
        return GameState(level=20, coin=20000, food=50, robot_levels={'spark':4,'nova':2}, active_robot='spark', egg_id='', rare_parts=20)

    def test_old_save_keeps_progress_and_new_inventory_survives_round_trip(self):
        before = self.state().to_dict()
        for key in ('weapon_levels','loadouts','rare_parts','weekly','tournament'):
            before.pop(key)
        state = GameState.from_dict(before)
        self.assertEqual(state.coin,20000)
        self.assertEqual(state.robot_levels,{'spark':4,'nova':2})
        self.assertTrue(perform(state,'weapon_buy',['laser'],1000).ok)
        self.assertTrue(perform(state,'weapon_equip',['laser','spark'],1000).ok)
        self.assertTrue(perform(state,'weapon_upgrade',['laser'],1000).ok)
        restored=GameState.from_dict(state.to_dict())
        self.assertEqual(restored.to_dict(),state.to_dict())

    def test_two_slots_no_duplicate_spending_and_swap_locked_in_battle(self):
        state=self.state()
        for weapon in ('laser','sword','drone'):
            self.assertTrue(perform(state,'weapon_buy',[weapon],1000).ok)
        balance=state.coin
        self.assertFalse(perform(state,'weapon_buy',['laser'],1000).ok)
        self.assertEqual(state.coin,balance)
        self.assertTrue(perform(state,'weapon_equip',['laser','spark'],1000).ok)
        self.assertTrue(perform(state,'weapon_equip',['sword','spark'],1000).ok)
        self.assertFalse(perform(state,'weapon_equip',['drone','spark'],1000).ok)
        perform(state,'battle_start',['spark'],1000)
        self.assertFalse(perform(state,'weapon_remove',['laser','spark'],1000).ok)
        self.assertEqual(restore_battle(state.battle),state.battle)
        before=state.clone()
        a=take_turn(state.battle,'attack',state.battle['id'],0)
        b=take_turn(before.battle,'attack',before.battle['id'],0)
        self.assertTrue(a.ok and b.ok)
        self.assertEqual(state.battle,before.battle)

    def test_weekly_reward_is_once_and_difficulty_scales_bots(self):
        state=self.state(); refresh_week(state,1_000_000)
        state.manual_taps+=500
        self.assertTrue(perform(state,'weekly_claim',['taps'],1_000_000).ok)
        before=state.to_dict()
        self.assertFalse(perform(state,'weekly_claim',['taps'],1_000_000).ok)
        self.assertEqual(before,state.to_dict())
        perform(state,'difficulty',['expert'],1_000_000)
        perform(state,'battle_start',['spark'],1_000_000)
        hard=state.battle['enemy_max_hp']
        other=self.state();perform(other,'battle_start',['spark'],1_000_000)
        self.assertGreater(hard,other.battle['enemy_max_hp'])
        self.assertGreater(state.battle['reward'],other.battle['reward'])

    def test_first_legacy_cloud_connection_keeps_offline_equipment_and_goals(self):
        from game_session import GameSession
        from local_store import MemoryStore

        store = MemoryStore()
        session = GameSession(store=store, clock=lambda: 1_000_000)
        session.state = self.state()
        refresh_week(session.state, 1_000_000)
        session.state.manual_taps += 500
        self.assertTrue(perform(session.state, 'weekly_claim', ['taps'], 1_000_000).ok)
        self.assertTrue(perform(session.state, 'weapon_buy', ['laser'], 1_000_000).ok)
        self.assertTrue(perform(session.state, 'weapon_upgrade', ['laser'], 1_000_000).ok)
        self.assertTrue(perform(session.state, 'weapon_equip', ['laser', 'spark'], 1_000_000).ok)
        perform(session.state, 'difficulty', ['expert'], 1_000_000)
        before = session.state.clone()
        session._merge_profile({'coin': 100, 'level': 3, 'base_click_power': 2})
        restored = GameSession(store=store, clock=lambda: 1_000_000)
        for key in ('weapon_levels', 'loadouts', 'weapon_upgrades', 'rare_parts',
                    'arena_difficulty', 'weekly', 'tournament'):
            self.assertEqual(getattr(session.state, key), getattr(before, key), key)
            self.assertEqual(getattr(restored.state, key), getattr(before, key), key)

    def test_newer_legacy_cloud_profile_does_not_replace_trusted_equipment(self):
        from game_session import GameSession
        from local_store import MemoryStore

        state = self.state()
        perform(state, 'weapon_buy', ['laser'], 1000)
        perform(state, 'weapon_equip', ['laser', 'spark'], 1000)
        refresh_week(state, 1000)
        store = MemoryStore({'schema': 2, 'state': state.to_dict(), 'trusted': True,
                             'saved_at': 1000, 'device_id': 'synthetic-cloud-check'})
        session = GameSession(store=store, clock=lambda: 1000)
        before = session.state.clone()
        session._merge_profile({'coin': 2000, 'level': 3, 'last_active_at': 1001})
        for key in ('weapon_levels', 'loadouts', 'rare_parts', 'weekly', 'tournament'):
            self.assertEqual(getattr(session.state, key), getattr(before, key), key)


class ArenaServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.now=1_000_000
        self.server=ArenaService(Path(self.temp.name)/'arena.sqlite',clock=lambda:self.now)
        self.a=self.server.register('Первый')
        self.b=self.server.register('Второй')

    def tearDown(self):
        self.temp.cleanup()

    def match(self):
        self.assertTrue(self.server.enqueue(self.a['id'],'spark','plasma')['waiting'])
        return self.server.enqueue(self.b['id'],'volt','sniper')['match']

    def test_only_humans_match_and_tokens_are_required(self):
        self.assertEqual(self.server.ranking().__len__(),2)
        self.assertEqual(self.server.authenticate(self.a['token']),self.a['id'])
        with self.assertRaises(RuleError): self.server.authenticate('wrong-token')
        match=self.match()
        self.assertEqual(match['kind'],'human-ranked')
        self.assertEqual({x['id'] for x in match['players'].values()},{self.a['id'],self.b['id']})

    def test_turn_ownership_and_retries_cannot_duplicate_damage_or_rating(self):
        match=self.match(); identity=match['id']
        with self.assertRaises(RuleError): self.server.turn(self.b['id'],identity,0,'command-0','attack')
        result=self.server.turn(self.a['id'],identity,0,'command-1','attack')
        self.assertEqual(self.server.turn(self.a['id'],identity,0,'command-1','attack'),result)
        self.assertEqual(self.server.current(self.b['id'])['state']['b']['hp'],105)
        with self.assertRaises(RuleError): self.server.turn(self.a['id'],identity,0,'command-2','attack')
        result=self.server.turn(self.b['id'],identity,1,'command-3','resign')
        self.assertEqual(result['result'],'finished')
        self.assertEqual(self.server.profile(self.a['id'])['rating'],1016)
        self.server.turn(self.b['id'],identity,1,'command-3','resign')
        self.assertEqual(self.server.profile(self.a['id'])['rating'],1016)

    def test_concurrent_turn_commands_commit_once(self):
        match=self.match()
        def command(index):
            try:return self.server.turn(self.a['id'],match['id'],0,f'command-{index}','attack')
            except RuleError:return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            result=list(pool.map(command,range(4)))
        self.assertEqual(sum(item is not None for item in result),1)
        self.assertEqual(self.server.current(self.a['id'])['revision'],1)

    def test_clan_war_counts_server_confirmed_wins_and_timeout_only_once(self):
        first=self.server.clan_action(self.a['id'],'create','Искры')['your_clan']
        second=self.server.clan_action(self.b['id'],'create','Вольты')['your_clan']
        self.server.clan_action(self.a['id'],'war',second)
        match=self.match()
        self.server.turn(self.b['id'],match['id'],0,'resign-command','resign')
        wars=self.server.clans(self.a['id'])['wars']
        war=wars[0]
        self.assertEqual(war['score_a']+war['score_b'],1)
        self.assertEqual(self.server.clans(self.a['id'])['clans'][0]['mission_wins'],1)
        self.assertTrue(first and second)
        match=self.match();self.now+=46
        self.server.current(self.b['id'])
        rating=self.server.profile(self.b['id'])['rating']
        self.server.current(self.b['id'])
        self.assertEqual(self.server.profile(self.b['id'])['rating'],rating)

    def test_player_cannot_join_two_clans_or_spend_unowned_tokens(self):
        clan=self.server.clan_action(self.a['id'],'create','Мастерская')['your_clan']
        self.server.clan_action(self.b['id'],'join',clan)
        with self.assertRaises(RuleError): self.server.clan_action(self.b['id'],'create','Другие')
        for _ in range(10):self.server.clan_action(self.b['id'],'donate')
        with self.assertRaises(RuleError):self.server.clan_action(self.b['id'],'donate')
        with self.assertRaises(RuleError):self.server.clan_action(self.b['id'],'mission')


if __name__=='__main__': unittest.main()
