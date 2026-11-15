import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]

import server.app as endpoint
from game_session import GameSession
from gameplay import GameState
from online_arena import OnlineArena
from server.arena_service import ArenaService


class ArenaHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_http_clients_use_server_state_and_keep_offline_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            arena=ArenaService(Path(directory)/'arena.sqlite')
            transport=httpx.ASGITransport(app=endpoint.app)
            original=httpx.AsyncClient

            def client(**kwargs):
                return original(transport=transport,**kwargs)

            first,second=GameSession.preview(),GameSession.preview()
            first.state=GameState(coin=777,robot_levels={'spark':3},active_robot='spark',egg_id='')
            second.state=GameState(coin=888,robot_levels={'volt':2},active_robot='volt',egg_id='')
            a,b=OnlineArena(first),OnlineArena(second)
            with patch.object(endpoint,'service',arena),patch('online_arena.httpx.AsyncClient',side_effect=client):
                await a.connect('http://arena.test','Первый игрок')
                await b.connect('http://arena.test','Второй игрок')
                self.assertFalse(a.error or b.error)
                await a.command('queue');await b.command('queue');await a.refresh()
                self.assertEqual(a.match['id'],b.match['id'])
                async with original(transport=transport) as direct:
                    denied=await direct.get('http://arena.test/me')
                    self.assertEqual(denied.status_code,401)
                    url='http://arena.test/match/'+a.match['id']+'/turn'
                    headers={'Authorization':'Bearer '+a.credentials['token']}
                    bogus=await direct.post(url,headers=headers,json={'revision':0,'command':'http-command-one','action':'attack','damage':999999,'winner':'a'})
                    self.assertEqual(bogus.status_code,200)
                    result=bogus.json()
                    self.assertGreater(result['state']['b']['hp'],0)
                    self.assertLess(result['state']['b']['hp'],result['state']['b']['max_hp'])
                    self.assertLess(result['state']['last']['damage'],60)
                    repeat=await direct.post(url,headers=headers,json={'revision':0,'command':'http-command-one','action':'attack'})
                    self.assertEqual(repeat.json(),result)
                self.assertEqual(first.state.coin,777)
                self.assertEqual(second.state.coin,888)
                self.assertEqual(first.state.robot_levels,{'spark':3})


if __name__=='__main__':unittest.main()
