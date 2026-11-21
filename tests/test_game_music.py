import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from game_music import music_payload, music_control
from game_session import GameSession
from local_store import MemoryStore


class GameMusicTests(unittest.TestCase):
    def setUp(self):
        self.session = GameSession.preview(SimpleNamespace(width=390,height=844,run_task=Mock()))

    def test_workshop_and_arena_music_follow_game_context(self):
        self.assertEqual(music_payload(self.session)['track'],'workshop')
        self.assertEqual(music_payload(self.session,2)['track'],'arena')
        self.session.focus_scene='battle'
        self.assertEqual(music_payload(self.session)['track'],'arena')

    def test_battle_resolution_does_not_interrupt_background_before_visual_victory(self):
        self.session.state.battle={'id':'b1','result':'win','turn':3}
        first=music_payload(self.session)
        self.session.arena_visual={'phase':'idle'}
        self.session.state.battle['turn']=4
        self.assertEqual(music_payload(self.session),first)
        self.session.state.battle['result']='loss'
        self.assertEqual(music_payload(self.session),first)

    def test_preview_action_does_not_recreate_background_music(self):
        self.session.preview_identity='volt'
        self.session.preview_action='victory'
        self.session.preview_event=3
        first=music_payload(self.session)
        self.session.preview_action='attack'
        self.assertEqual(music_payload(self.session),first)

    def test_global_toggle_uses_presentation_settings_without_changing_game_state(self):
        control=music_control(self.session)
        before=self.session.state.to_dict()
        with patch.object(self.session,'persist'):
            control.on_sound_change(SimpleNamespace(data=json.dumps({'enabled':False})))
        self.assertFalse(self.session.motion_sound)
        self.assertEqual(self.session.state.to_dict(),before)
        self.assertFalse(music_payload(self.session)['sound'])

    def test_pause_and_resume_intents_are_semantic(self):
        self.session._paused=True
        self.assertTrue(music_payload(self.session)['paused'])
        self.session._paused=False
        self.assertFalse(music_payload(self.session)['paused'])

    def test_mute_preference_survives_save_reload_without_touching_player_state(self):
        store=MemoryStore()
        session=GameSession(store=store,clock=lambda:1000)
        session.presentation(sound=False)
        self.assertFalse(store.load()['presentation']['motion_sound'])
        restored=GameSession(store=store,clock=lambda:1000)
        self.assertFalse(restored.motion_sound)
        restored.presentation(sound=True)
        self.assertTrue(GameSession(store=store,clock=lambda:1000).motion_sound)


if __name__=='__main__':unittest.main()
