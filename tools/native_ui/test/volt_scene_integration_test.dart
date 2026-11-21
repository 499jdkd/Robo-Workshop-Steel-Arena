import 'package:flet_rive/flet_rive.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/volt_motion.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

GameSceneClock createScene({
  bool arena = false,
  bool demo = false,
  String player = 'volt',
  String enemy = 'spark',
}) {
  final scene = GameSceneClock()..viewport = const Size(844, 390);
  scene.update({
    'arena': arena,
    'demonstration': demo,
    'expanded': true,
    'robot': player,
    'enemy': enemy,
    'mobility': player == 'volt' ? 'hover' : 'wheels',
    'enemyMobility': enemy == 'volt' ? 'hover' : 'wheels',
    'phase': arena ? 'idle' : 'workshop',
    'action': 'idle',
    'combatAction': 'idle',
    'enemyAction': 'idle',
    'enemyCombatAction': 'idle',
    'weapon': 'electric',
    'enemyWeapon': 'electric',
    'equipped': <String>[],
    'enemyEquipped': <String>[],
    'sound': false,
    'event': 'initial',
    'result': 'active',
    'prepareSeconds': .4,
    'flightSeconds': .72,
    'impactSeconds': .25,
  });
  scene.advance(0);
  addTearDown(scene.dispose);
  return scene;
}

void finitePose(GamePose pose) {
  expect(pose.values.values.every((number) => number.isFinite), isTrue);
  expect(pose.extra.values.every((number) => number.isFinite), isTrue);
}

String legacyAction(String action) => switch (action) {
  'quick' => 'attack',
  'ultimate' => 'special',
  _ => action,
};

void main() {
  test('spaced touches use seven distinct shuffled Volt reactions', () {
    final scene = createScene(demo: true);
    final signatures = <String>{};
    final actions = <String>{};
    for (var i = 0; i < 7; i++) {
      scene.react();
      final action = scene.localAction;
      actions.add(action);
      scene.advance(0);
      scene.advance(voltActionSeconds[action]! * .35);
      expect(scene.playerVoltFrame!.action, action);
      final pose = scene.player.pose;
      finitePose(pose);
      signatures.add(
        '${pose.y}:${pose.head}:${pose.armL}:${pose.extra['joint0']}',
      );
      if (action == 'jump') expect(pose.y, lessThan(-25));
      if (action == 'surprise') expect(pose.shock, greaterThan(.5));
      scene.advance(voltActionSeconds[action]! + .6);
    }
    expect(signatures.length, 7);
    expect(actions, {
      'joy',
      'jump',
      'surprise',
      'inspect',
      'dance',
      'playful',
      'wave',
    });
  });

  test(
    'third rapid touch produces annoyance without awarding or replaying an attack',
    () {
      final scene = createScene();
      scene.react();
      scene.advance(.1);
      scene.react();
      scene.advance(.1);
      scene.react();
      scene.advance(0);
      scene.advance(.3);
      expect(scene.tapBurst, 3);
      expect(scene.localAction, 'anger');
      expect(scene.playerVoltFrame!.action, 'anger');
      expect(scene.player.pose.brow, greaterThan(.2));
      expect(scene.playerVoltFrame!.discharge, 0);
    },
  );

  test('touch interruptions blend the head, body and coil actuators', () {
    final scene = createScene(demo: true);
    scene.showcase('jump');
    scene.advance(0);
    scene.advance(.5);
    final previous = scene.player.pose;
    scene.showcase('surprise');
    scene.advance(0);
    expect(scene.player.pose.y, closeTo(previous.y, 1e-8));
    expect(
      scene.player.pose.extra['joint0'],
      closeTo(previous.extra['joint0']!, 1e-8),
    );
    scene.advance(.016);
    expect((scene.player.pose.y - previous.y).abs(), lessThan(8));
    scene.advance(.25);
    expect(scene.playerVoltFrame!.action, 'surprise');
    finitePose(scene.player.pose);
  });

  test('head and eyes follow both directions of the pointer', () {
    final scene = createScene(demo: true);
    final baseline = scene.player.pose.head;
    scene.pointAt(const Offset(820, 20));
    scene.advance(0);
    final right = scene.player.pose.head;
    expect(scene.gaze.dx, greaterThan(0));
    expect(right, greaterThan(baseline));
    scene.pointAt(const Offset(0, 20));
    scene.advance(0);
    expect(scene.gaze.dx, lessThan(0));
    expect(scene.player.pose.head, lessThan(right));
    scene.player.facing = -1;
    scene.pointAt(const Offset(820, 20));
    scene.advance(0);
    expect(
      scene.gaze.dx,
      lessThan(0),
      reason:
          'Mirrored local eye coordinates must follow the same screen point',
    );
  });

  test(
    'selected floor point moves Volt through local locomotion inside the viewport',
    () {
      final scene = createScene();
      final original = scene.player.center;
      scene.moveTo(const Offset(820, 300));
      for (var frame = 0; frame < 120; frame++) scene.advance(1 / 60);
      expect(scene.player.center, greaterThan(original + 50));
      expect(
        scene.player.center + 210 * scene.scale,
        lessThanOrEqualTo(scene.viewport.width),
      );
      expect(scene.player.motor.distance, greaterThan(0));
      expect(scene.player.facing, 1);
    },
  );

  test(
    'lifecycle, hidden route and ad pause freeze the local Volt animation clock',
    () {
      for (final mode in ['lifecycle', 'hidden', 'ad']) {
        final scene = createScene();
        scene.showcase('ultimate');
        scene.advance(0);
        scene.advance(.5);
        final before = [
          scene.clock,
          scene.age,
          scene.localAge,
          scene.playerVoltFrame!.t,
        ];
        if (mode == 'lifecycle') scene.suspended = true;
        if (mode == 'hidden') scene.hidden = true;
        if (mode == 'ad') scene.update({...scene.data, 'paused': true});
        scene.advance(30);
        expect(
          [scene.clock, scene.age, scene.localAge, scene.playerVoltFrame!.t],
          before,
          reason: mode,
        );
        scene.suspended = scene.hidden = false;
        scene.update({...scene.data, 'paused': false});
        scene.advance(.1);
        expect(scene.clock, greaterThan(before.first));
      }
    },
  );

  for (final nextArena in [false, true]) {
    test(
      'leaving Volt demo resets effects and camera before ${nextArena ? 'battle' : 'workshop'} paints',
      () {
        final scene = createScene(demo: true);
        scene.showcase('ultimate');
        scene.advance(0);
        scene.advance(.9);
        scene.camera(1.8);
        scene.advance(.2);
        scene.pan = const Offset(30, 12);
        scene.gaze = const Offset(8, -5);
        scene.effects.burst(const Offset(100, 100), Colors.cyan);
        var staleBurst = false;
        scene.pendingBurst = () => staleBurst = true;
        scene.update({
          ...scene.data,
          'demonstration': false,
          'arena': nextArena,
          'phase': nextArena ? 'idle' : 'workshop',
          'action': 'idle',
          'combatAction': 'idle',
          'event': 'left-demo',
        });
        expect(scene.localAction, isEmpty);
        expect(scene.effects.particles, isEmpty);
        expect(scene.pendingBurst, isNull);
        expect(scene.zoom, 1);
        expect(scene.zoomTarget, 1);
        expect(scene.pan, Offset.zero);
        expect(scene.gaze, Offset.zero);
        expect(scene.inspecting, isFalse);
        scene.advance(0);
        expect(staleBurst, isFalse);
        expect(scene.playerVoltFrame!.action, 'idle');
        expect(
          scene.player.pose.y,
          greaterThan(-30),
          reason: 'The old hovering-super pose must not blend into a new route',
        );
        expect(scene.effects.particles, isEmpty);
      },
    );
  }

  const actions = [
    'attack',
    'quick',
    'special',
    'guard',
    'dodge',
    'charge',
    'ultimate',
    'victory',
    'defeat',
  ];
  for (final opponent in [false, true]) {
    for (final action in actions) {
      test(
        '${opponent ? 'enemy' : 'player'} Volt maps $action to its own articulated frame',
        () {
          final scene = createScene(
            arena: true,
            player: opponent ? 'spark' : 'volt',
            enemy: opponent ? 'volt' : 'spark',
          );
          if (action == 'victory' || action == 'defeat') {
            final wins = action == 'victory';
            final ownWins = opponent ? !wins : wins;
            scene.update({
              ...scene.data,
              'phase': 'idle',
              'result': ownWins ? 'win' : 'loss',
              'event': 'outcome',
            });
            scene.advance(0);
            scene.advance(.6);
          } else {
            final defensive = {'guard', 'dodge', 'charge'}.contains(action);
            scene.update({
              ...scene.data,
              'phase': opponent
                  ? 'enemy-flight'
                  : defensive
                  ? 'approach'
                  : 'flight',
              'action': opponent ? 'idle' : legacyAction(action),
              'combatAction': opponent ? 'idle' : action,
              'enemyAction': opponent ? legacyAction(action) : 'idle',
              'enemyCombatAction': opponent ? action : 'idle',
              'event': '$action-${opponent ? 'enemy' : 'player'}',
            });
            scene.advance(0);
            scene.advance(
              opponent
                  ? .4
                  : defensive
                  ? .4
                  : .2,
            );
          }
          final frame = opponent ? scene.enemyVoltFrame : scene.playerVoltFrame;
          final actor = opponent ? scene.enemy : scene.player;
          expect(frame, isNotNull);
          expect(frame!.action, action);
          expect(frame.t, greaterThan(0));
          finitePose(actor.pose);
          expect(
            actor.pose.weapon,
            isEmpty,
            reason: 'Built-in coils must not be replaced by the universal gun',
          );
          if (action == 'guard') expect(frame.shield, greaterThan(.5));
          if (action == 'dodge') expect(frame.trail, greaterThan(.3));
          if (action == 'charge') expect(frame.charge, greaterThan(.5));
          if (action == 'ultimate')
            expect(frame.charge + frame.discharge, greaterThan(.5));
        },
      );
    }
  }

  test(
    'equipped player and enemy modules remain visible during their real selected attack',
    () {
      final scene = createScene(arena: true, player: 'volt', enemy: 'volt');
      scene.update({
        ...scene.data,
        'equipped': ['laser', 'sniper'],
        'weapon': 'sniper',
        'enemyEquipped': ['rocket'],
        'enemyWeapon': 'rocket',
        'phase': 'flight',
        'action': 'attack',
        'combatAction': 'attack',
        'event': 'own-shot',
      });
      scene.advance(0);
      scene.advance(.25);
      expect(scene.player.pose.weapon, 'sniper');
      expect(scene.player.pose.deploy, greaterThan(0));
      scene.update({
        ...scene.data,
        'phase': 'enemy-flight',
        'enemyAction': 'attack',
        'enemyCombatAction': 'attack',
        'event': 'enemy-shot',
      });
      scene.advance(0);
      scene.advance(.4);
      expect(scene.enemy.pose.weapon, 'rocket');
      expect(scene.enemy.pose.deploy, greaterThan(0));
    },
  );

  for (final opponent in [false, true]) {
    test(
      '${opponent ? 'enemy' : 'player'} defeat reaches zero power and survives later UI updates',
      () {
        final scene = createScene(
          arena: true,
          player: opponent ? 'spark' : 'volt',
          enemy: opponent ? 'volt' : 'spark',
        );
        scene.update({
          ...scene.data,
          'phase': 'idle',
          'result': opponent ? 'win' : 'loss',
          'event': 'defeat',
        });
        scene.advance(0);
        scene.advance(voltActionSeconds['defeat']! + .1);
        final frame = opponent ? scene.enemyVoltFrame! : scene.playerVoltFrame!;
        final actor = opponent ? scene.enemy : scene.player;
        expect(frame.action, 'defeat');
        expect(frame.t, 1);
        expect(frame.power, 0);
        expect(frame.coilGlow, 0);
        expect(frame.coreGlow, 0);
        expect(actor.pose.sad, 1);
        scene.update({...scene.data, 'event': 'later-ui-update'});
        scene.advance(0);
        final later = opponent ? scene.enemyVoltFrame! : scene.playerVoltFrame!;
        expect(later.power, 0);
        expect(later.action, 'defeat');
      },
    );
  }
}
