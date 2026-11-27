import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/game_scene.dart';
import 'package:flet_rive/src/robot/robot_audio.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  GameSceneClock create(
    String robot,
    List<RobotAudioCue> cues, {
    bool arena = false,
  }) {
    final scene = GameSceneClock(onCharacterCue: cues.add)
      ..viewport = const Size(844, 390);
    scene.update({
      'robot': robot,
      'enemy': 'titan',
      'arena': arena,
      'demonstration': true,
      'expanded': true,
      'sound': true,
      'phase': arena ? 'idle' : 'workshop',
      'action': 'idle',
      'combatAction': 'idle',
      'enemyAction': 'idle',
      'enemyCombatAction': 'attack',
      'weapon': 'laser',
      'enemyWeapon': 'rocket',
      'enemyEquipped': ['rocket'],
      'event': 'battle:1:0:idle',
      'result': 'active',
      'prepareSeconds': .4,
      'flightSeconds': .72,
      'impactSeconds': .25,
    });
    scene.advance(0);
    addTearDown(scene.dispose);
    return scene;
  }

  void run(GameSceneClock scene, double seconds) {
    for (var i = 0; i < (seconds * 60).ceil(); i++) scene.advance(1 / 60);
  }

  test(
    'all 32 workshop characters answer a touch and have audible dance beats',
    () {
      for (final id in robotVoices.keys) {
        final cues = <RobotAudioCue>[];
        final scene = create(id, cues);
        scene.react();
        run(scene, .8);
        expect(cues, isNotEmpty, reason: '$id touch');
        expect(cues.every((c) => c.channel.startsWith('player:')), isTrue);
        cues.clear();
        scene.showcase('dance');
        run(scene, 2.3);
        expect(
          cues
              .where(
                (c) =>
                    c.name.startsWith('robot_dance_') ||
                    id == 'titan' && c.name == 'titan_step',
              )
              .length,
          greaterThanOrEqualTo(3),
          reason: '$id dance',
        );
      }
    },
  );

  test('all 30 unchanged rigs play a shot at the preview release, once', () {
    for (final id in robotVoices.keys.where(
      (id) => !{'volt', 'titan'}.contains(id),
    )) {
      final cues = <RobotAudioCue>[];
      final scene = create(id, cues);
      scene.showcase('attack');
      run(scene, .38);
      expect(cues.where((c) => c.name == 'laser'), isEmpty, reason: id);
      run(scene, .1);
      expect(cues.where((c) => c.name == 'laser').length, 1, reason: id);
      scene.update({...scene.data});
      run(scene, 1.2);
      expect(cues.where((c) => c.name == 'laser').length, 1, reason: id);
    }
  });
  test(
    'Titan authored release uses the equipped sound once and respects mute history',
    () {
      final cues = <RobotAudioCue>[];
      final scene = create('titan', cues);
      scene.update({
        ...scene.data,
        'equipped': ['laser'],
      });
      scene.showcase('attack');
      run(scene, 1.1);
      expect(cues.where((c) => c.name == 'laser'), isEmpty);
      run(scene, .05);
      expect(cues.where((c) => c.name == 'laser').length, 1);
      scene.update({...scene.data});
      run(scene, 1);
      expect(cues.where((c) => c.name == 'laser').length, 1);
      cues.clear();
      scene.audio.muted = true;
      scene.showcase('ultimate');
      run(scene, 3.4);
      expect(cues, isEmpty);
      scene.audio.muted = false;
      run(scene, .2);
      expect(cues, isEmpty);
    },
  );

  test(
    'Titan quick combo sounds each alternating contact and fires mounted gear on its arm',
    () {
      for (final equipped in [false, true]) {
        final cues = <RobotAudioCue>[];
        final scene = create('titan', cues);
        scene.update({
          ...scene.data,
          'equipped': equipped ? ['laser'] : [],
        });
        scene.showcase('quick');
        run(scene, 1.1);
        final contacts = cues.where(
          (c) => {'titan_ram', 'impact', 'laser'}.contains(c.name),
        );
        expect(contacts.map((c) => c.name), [
          equipped ? 'laser' : 'titan_ram',
          'impact',
          equipped ? 'laser' : 'titan_ram',
          'impact',
        ]);
        expect(contacts.every((c) => c.channel == 'player:action'), true);
        scene.update({...scene.data});
        run(scene, .3);
        expect(
          cues
              .where((c) => {'titan_ram', 'impact', 'laser'}.contains(c.name))
              .length,
          4,
        );
      }
    },
  );

  test(
    'battle phases keep one timeline through Flet updates and a new turn repeats it',
    () {
      final cues = <RobotAudioCue>[];
      final scene = create('spark', cues, arena: true);
      void phase(String name, {int turn = 1}) => scene.update({
        ...scene.data,
        'phase': name,
        'action': 'attack',
        'combatAction': 'attack',
        'event': 'battle:$turn:$turn:$name',
      });
      phase('approach');
      run(scene, .4);
      expect(cues.where((c) => c.name == 'laser'), isEmpty);
      phase('flight');
      run(scene, .72);
      phase('impact');
      run(scene, .25);
      expect(cues.where((c) => c.name == 'laser').length, 1);
      phase('enemy-flight');
      run(scene, .72);
      phase('reply');
      run(scene, .25);
      expect(cues.where((c) => c.name == 'rocket').length, 1);
      expect(
        cues.where((c) => c.name == 'rocket').single.channel,
        'enemy:action',
      );
      phase('approach', turn: 2);
      run(scene, .4);
      phase('flight', turn: 2);
      run(scene, .2);
      expect(cues.where((c) => c.name == 'laser').length, 2);
    },
  );

  test(
    'muting advances history; hidden, paused and suspended scenes emit nothing',
    () {
      final cues = <RobotAudioCue>[];
      final scene = create('arachna', cues);
      scene.audio.muted = true;
      scene.showcase('dance');
      run(scene, 2.3);
      expect(cues, isEmpty);
      scene.audio.muted = false;
      run(scene, .1);
      expect(cues, isEmpty);
      for (final condition in ['hidden', 'paused', 'suspended']) {
        scene.showcase('dance');
        scene.hidden = condition == 'hidden';
        scene.suspended = condition == 'suspended';
        scene.update({...scene.data, 'paused': condition == 'paused'});
        final clock = scene.clock;
        run(scene, 3);
        expect(cues, isEmpty, reason: condition);
        expect(scene.clock, clock);
        scene.hidden = scene.suspended = false;
        scene.update({...scene.data, 'paused': false});
      }
    },
  );

  test(
    'switching robot replaces the response and outcome channels stay separate',
    () {
      final cues = <RobotAudioCue>[];
      final scene = create('spark', cues);
      scene.showcase('dance');
      run(scene, .3);
      cues.clear();
      scene.update({...scene.data, 'robot': 'titan', 'event': 'next'});
      scene.react();
      run(scene, .4);
      expect(cues.any((c) => c.name == 'robot_reply_heavy'), isTrue);
      expect(cues.any((c) => c.name.startsWith('robot_dance_')), isFalse);
      scene.update({
        ...scene.data,
        'arena': true,
        'enemy': 'spark',
        'phase': 'victory',
        'result': 'win',
        'event': 'battle:3:1:victory',
      });
      cues.clear();
      run(scene, .4);
      expect(cues.any((c) => c.channel == 'player:reaction'), isTrue);
      expect(cues.any((c) => c.channel == 'enemy:reaction'), isTrue);
    },
  );
}
