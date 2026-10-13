#!/usr/bin/env python3
"""Exercise standalone clip arming with synthetic ROS inputs on loopback DDS 96.

This checks controller transitions and reference playback, not robot balance.
No simulator, camera, bridge, or physical robot is used.
"""

import argparse
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import time

from planner_graph_smoke import stop_process

ROOT = Path(__file__).resolve().parents[1]
TRACKING = 'sonic engaged: track from frame 0'
PREPPED = 'prepped on frame 0'
STANDING = 'sonic engaged: STAND'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', choices=['walk', 'parkour', 'repose', 'uolm'])
    parser.add_argument('--logs', type=Path,
                        default=ROOT / '.migration/motion-path')
    args = parser.parse_args()
    os.environ.update(ROS_DOMAIN_ID='96',
                      RMW_IMPLEMENTATION='rmw_cyclonedds_cpp')
    os.environ['CYCLONEDDS_URI'] = (
        '<CycloneDDS><Domain><General><Interfaces>'
        '<NetworkInterface name="lo" /></Interfaces></General></Domain></CycloneDDS>')

    import numpy as np
    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import Joy
    from unitree_hg.msg import LowCmd, LowState
    from vision_encoders.msg import ImageTokens

    rclpy.init()
    node = rclpy.create_node('motion_path_smoke')
    prefix = '/motion_path_smoke/'
    state_pub = node.create_publisher(LowState, prefix + 'lowstate', 10)
    joy_pub = node.create_publisher(Joy, prefix + 'joy', 10)
    tokens_pub = node.create_publisher(
        ImageTokens, prefix + 'tokens',
        QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
    commands = []
    command_sub = node.create_subscription(
        LowCmd, prefix + 'lowcmd', commands.append, 10)

    specs = json.loads((ROOT / 'data/sample/samples.json').read_text())['samples']
    artifacts = Path(os.environ.get('VIBE_ARTIFACT_ROOT', ROOT / 'artifacts'))
    args.logs.mkdir(parents=True, exist_ok=True)
    try:
        for name, spec in specs.items():
            if args.sample and name != args.sample:
                continue
            policy = artifacts / spec['policy']
            manifest = json.loads(policy.with_suffix('.manifest.json').read_text())
            motion = ROOT / 'data/sample' / name / 'motion.npz'
            with np.load(motion) as clip:
                duration = len(clip['joint_pos']) / float(clip['fps'][0])
            state = LowState()
            state.imu_state.quaternion = [1., 0., 0., 0.]
            for motor, angle in zip(state.motor_state, manifest['action']['default_joint_pos']):
                motor.q = float(angle)
            joy = Joy()
            joy.axes = [0.] * 8
            joy.buttons = [0] * 12
            tokens = ImageTokens()
            tokens.header.frame_id = 'theia-tiny'
            tokens.grid_h, tokens.grid_w, tokens.dim = 3, 7, 192
            tokens.patches = [0.] * (21 * 192)
            tokens.cls = [0.] * 192
            logfile = args.logs / (name + '.log')
            command = [
                'ros2', 'run', 'cpp_control', 'g1_vibe_sonic_node', '--ros-args',
                '-p', 'config_path:=' + str(ROOT / 'cyclonedds_ws/src/cpp_control/config/vibe/g1_vibe_sonic.yaml'),
                '-p', 'onnx_path:=' + str(policy),
                '-p', 'motion_path:=' + str(motion), '-p', 'il_ordered:=true',
                '-p', 'goal_color:=' + str(spec.get('goal_color', 0)),
                '-r', '/lowstate:=' + prefix + 'lowstate',
                '-r', '/lowcmd:=' + prefix + 'lowcmd',
                '-r', '/joy:=' + prefix + 'joy',
                '-r', '/enc/tokens:=' + prefix + 'tokens']
            with logfile.open('w') as log:
                process = subprocess.Popen(command, stdout=log,
                                           stderr=subprocess.STDOUT,
                                           start_new_session=True)
                try:
                    def read_log():
                        return logfile.read_text()

                    def pump(seconds, send_tokens=True):
                        deadline = time.monotonic() + seconds
                        while time.monotonic() < deadline:
                            assert process.poll() is None, read_log()[-4000:]
                            state.tick += 1
                            state_pub.publish(state)
                            joy_pub.publish(joy)
                            if send_tokens:
                                tokens.header.stamp = node.get_clock().now().to_msg()
                                tokens_pub.publish(tokens)
                            rclpy.spin_once(node, timeout_sec=0.)
                            time.sleep(.01)

                    def wait_for(text, since=0, timeout=5.):
                        deadline = time.monotonic() + timeout
                        while text not in read_log()[since:]:
                            assert time.monotonic() < deadline, (
                                f'{name}: missing {text!r}\n' + read_log()[-4000:])
                            pump(.04)

                    wait_for('tokens flowing:', timeout=20.)
                    for input_kind in ['gamepad', 'joy']:
                        def press(button, send_tokens=True):
                            start = len(read_log())
                            if input_kind == 'gamepad':
                                bits = {'RB': 0, 'L1': 1, 'A': 8, 'Y': 11}
                                remote = bytearray(40)
                                struct.pack_into('<H', remote, 2, 1 << bits[button])
                                state.wireless_remote = list(remote)
                            else:
                                joy.buttons[{'RB': 5, 'L1': 4, 'A': 0, 'Y': 3}[button]] = 1
                            pump(.06, send_tokens)
                            state.wireless_remote = [0] * 40
                            joy.buttons = [0] * 12
                            pump(.06, send_tokens)
                            return start

                        wait_for(STANDING, press('RB'))
                        start = press('A')
                        assert TRACKING not in read_log()[start:], 'A bypassed prep'
                        start = press('L1')
                        press('A')
                        assert TRACKING not in read_log()[start:], 'A bypassed unfinished prep'
                        wait_for(PREPPED, start)

                        start = press('A')
                        wait_for(TRACKING, start)
                        assert 'entry refused' not in read_log()[start:], read_log()[start:]
                        wait_for('motion finished', start, timeout=duration + 3.)
                        assert commands, 'Tracker did not emit commands'
                        assert all(math.isfinite(m.q) for m in commands[-1].motor_cmd[:29])

                        # RB invalidates prep; a failed token check must not.
                        wait_for(STANDING, press('RB'))
                        start = press('A')
                        assert TRACKING not in read_log()[start:], 'RB retained old prep'
                        start = press('L1')
                        wait_for(PREPPED, start)
                        pump(.25, send_tokens=False)
                        start = press('A', send_tokens=False)
                        assert TRACKING not in read_log()[start:], 'A bypassed stale tokens'
                        pump(.15)
                        start = press('A')
                        wait_for(TRACKING, start)

                        # Y must invalidate prep and command damping.
                        wait_for(STANDING, press('RB'))
                        start = press('L1')
                        wait_for(PREPPED, start)
                        start = press('Y')
                        pump(.1)
                        assert all(m.kp == 0. and m.kd == 5.
                                   for m in commands[-1].motor_cmd[:29]), 'Y did not damp'
                        press('A')
                        assert TRACKING not in read_log()[start:], 'Y retained old prep'
                        print(f'PASS {name}/{input_kind}: prep gates, token retry, '
                              'full clip playback, RB reset, Y damping', flush=True)
                        commands.clear()
                except BaseException:
                    print(read_log()[-5000:], flush=True)
                    raise
                finally:
                    stop_process(process)
    finally:
        node.destroy_subscription(command_sub)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
