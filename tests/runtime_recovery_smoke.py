#!/usr/bin/env python3
"""Camera recovery and optional bridge lifetime on loopback DDS domain 97.

Uses the installed nodes and released encoder. Synthetic state goes only to the
planner's remapped input; no joystick input or physical robot is used.
"""

import argparse
import os
from pathlib import Path
import re
import signal
import socket
import struct
import subprocess
import time

from planner_graph_smoke import stop_process

ROOT = Path(__file__).resolve().parents[1]
PREFIX = '/runtime_recovery/'


def listener(port=0):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(4)
    server.setblocking(False)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs', type=Path, default=ROOT / '.migration/runtime-recovery')
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    os.environ.update(ROS_DOMAIN_ID='97', RMW_IMPLEMENTATION='rmw_cyclonedds_cpp',
                      ROS_LOG_DIR=str(args.logs.resolve() / 'ros'),
                      PYTHONDONTWRITEBYTECODE='1')
    os.environ['CYCLONEDDS_URI'] = (
        '<CycloneDDS><Domain><General><Interfaces>'
        '<NetworkInterface name="lo" /></Interfaces></General></Domain></CycloneDDS>')
    import cv2
    import numpy as np
    import rclpy
    import yaml
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from sledgehammer.msg import CubeObservation, PlannerStatus
    from sensor_msgs.msg import Image
    from unitree_hg.msg import LowCmd, LowState
    from vision_encoders.msg import ImageTokens

    rclpy.init()
    node = rclpy.create_node('runtime_recovery_smoke')
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
    tokens, frames, observations, statuses, commands = [], [], [], [], []
    subscriptions = [
        node.create_subscription(ImageTokens, PREFIX + 'tokens', tokens.append, qos),
        node.create_subscription(Image, PREFIX + 'frame', frames.append, qos),
        node.create_subscription(CubeObservation, PREFIX + 'observation', observations.append, qos),
        node.create_subscription(PlannerStatus, PREFIX + 'status', statuses.append, qos),
        node.create_subscription(LowCmd, '/lowcmd', commands.append, qos),
    ]
    state_pub = node.create_publisher(LowState, PREFIX + 'planner_state', 10)
    state = LowState()
    state.imu_state.quaternion = [1., 0., 0., 0.]

    def pump(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            state_pub.publish(state)
            rclpy.spin_once(node, timeout_sec=0.01)

    def wait_for(predicate, process, description, timeout=5.):
        end = time.monotonic() + timeout
        while not predicate():
            assert process.poll() is None, description + ': process exited'
            assert time.monotonic() < end, description + ': timed out'
            pump(.02)

    def accept(server, process):
        peers = []

        def ready():
            try:
                peers.append(server.accept()[0])
                peers[0].settimeout(1.)
                return True
            except BlockingIOError:
                return False

        wait_for(ready, process, 'camera connection', timeout=30.)
        return peers[0]

    def shutdown(process, label):
        start = time.monotonic()
        process.send_signal(signal.SIGINT)
        process.wait(timeout=1.5)
        assert process.returncode == 0, label + ': unclean shutdown'
        print(f'PASS {label}: SIGINT in {time.monotonic() - start:.3f}s', flush=True)

    pixels = np.full((63, 112, 3), 100, dtype=np.uint8)
    ok, encoded = cv2.imencode('.png', pixels)
    assert ok
    png = encoded.tobytes()
    depth = np.full((63, 112), 1000, dtype='<u2').tobytes()

    def plane(kind, fmt, data):
        return struct.pack('<BBHHffffI', kind, fmt, 112, 63,
                           100., 100., 55.5, 31., len(data)) + data

    rgbd = b'VD1\x02' + plane(0, 2, png) + plane(1, 0, depth)
    packet = struct.pack('<I', len(rgbd)) + rgbd
    artifacts = Path(os.environ.get('VIBE_ARTIFACT_ROOT', ROOT / 'artifacts'))

    try:
        for kind in ['encoder', 'planner', 'observe']:
            server = listener()
            port = server.getsockname()[1]
            config = yaml.safe_load((ROOT / 'cyclonedds_ws/src/sledgehammer/config/repose_planner/g1_sim_v9_3.yaml').read_text())
            config['camera']['port'] = port
            config_path = args.logs.resolve() / (kind + '.yaml')
            config_path.write_text(yaml.safe_dump(config))
            if kind == 'encoder':
                binary = ROOT / 'cyclonedds_ws/install/vision_encoders/lib/vision_encoders/encoder_node'
                params = ['-p', 'model_path:=' + str(artifacts / 'encoders/theia-tiny.onnx'),
                          '-p', 'camera_port:=' + str(port),
                          '-p', 'tokens_topic:=' + PREFIX + 'tokens',
                          '-p', 'frame_topic:=' + PREFIX + 'frame']
                count = lambda: len(tokens)
            else:
                name = 'g1_repose_planner_node' if kind == 'planner' else 'g1_repose_planner_observe_node'
                binary = ROOT / 'cyclonedds_ws/install/sledgehammer/lib/sledgehammer' / name
                params = ['-p', 'config_path:=' + str(config_path),
                          '-p', 'lowstate_topic:=' + PREFIX + 'planner_state',
                          '-p', 'planner_status_topic:=' + PREFIX + 'status'] if kind == 'planner' else [
                              '-p', 'config_path:=' + str(config_path),
                              '-p', 'observation_topic:=' + PREFIX + 'observation']
                count = (lambda: statuses[-1].n_reads if statuses else 0) if kind == 'planner' else lambda: len(observations)
            command = [str(binary), '--ros-args', *params]
            logfile = args.logs / (kind + '.log')
            peer = process = None
            with logfile.open('w') as log:
                try:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    peer = accept(server, process)
                    pump(.7)  # DDS discovery, within the frame timeout.

                    def good_frame(fragmented=False):
                        pump(.1)
                        before = count()
                        if fragmented:
                            peer.sendall(packet[:2])
                            pump(.05)
                            peer.sendall(packet[2:200])
                            pump(.05)
                            assert count() == before, 'partial frame was published'
                            peer.sendall(packet[200:])
                        else:
                            peer.sendall(packet)
                        wait_for(lambda: count() > before, process, kind + ' consumes frame', 1.5)
                        if kind == 'encoder':
                            wait_for(lambda: bool(frames), process, 'encoder frame')
                            assert bytes(frames[-1].data) == pixels.tobytes(), 'native pixels changed'
                            assert len(tokens[-1].patches) == 21 * 192
                            assert np.isfinite(tokens[-1].patches).all()

                    good_frame(fragmented=True)
                    for fault in [b'', packet[:2], packet[:-11]]:
                        peer.sendall(fault)
                        start = time.monotonic()
                        new_peer = accept(server, process)
                        assert time.monotonic() - start < 4., 'reconnect exceeded frame deadline'
                        peer.close()
                        peer = new_peer
                        good_frame()
                    print(f'PASS {kind}: fragmented frames and recovery from silence/partial header/partial payload', flush=True)

                    peer.close()
                    peer = None
                    server.close()
                    pump(.3)
                    server = listener(port)
                    peer = accept(server, process)
                    good_frame()
                    print(f'PASS {kind}: server restart resumes frame processing', flush=True)

                    # Keep the peer open: shutdown must not need its cooperation.
                    peer.sendall(packet[:7])
                    shutdown(process, kind + ' during partial frame')
                finally:
                    if peer is not None:
                        peer.close()
                    server.close()
                    if process is not None:
                        stop_process(process)

            # No server: the two-second retry delay must also be interruptible.
            with (args.logs / (kind + '-retry.log')).open('w') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                try:
                    wait_for(lambda: 'retrying' in (args.logs / (kind + '-retry.log')).read_text(),
                             process, kind + ' retry starts', timeout=30.)
                    shutdown(process, kind + ' during retry')
                finally:
                    stop_process(process)

        # Separate loopback address avoids the manual bridge's usual 127.0.0.1.
        logfile = args.logs / 'bridge-launch.log'
        command = ['ros2', 'launch', 'cpp_control', 'g1_vibe_sonic.launch.py',
                   'policy_path:=' + str(artifacts / 'models/walk/policy.onnx'),
                   'encoder_path:=' + str(artifacts / 'encoders/theia-tiny.onnx'),
                   'camera_ip:=127.0.0.2', 'bridge_address:=127.0.0.2']
        with logfile.open('w') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            children = {}
            try:
                wait_for(lambda: 'g1_vibe ready:' in logfile.read_text() and bool(commands),
                         process, 'tracker launch ready', timeout=40.)
                for name, pid in re.findall(r'\[([\w]+)-\d+\]: process started with pid \[(\d+)\]',
                                            logfile.read_text()):
                    children[name] = int(pid)
                assert set(children) == {'cdr_tcp_bridge', 'encoder_node', 'g1_vibe_sonic_node'}, children
                # A client disconnect must not end the server or control.
                with socket.create_connection(('127.0.0.2', 5556), timeout=2.):
                    pump(.1)
                pump(.3)
                os.kill(children['cdr_tcp_bridge'], 0)
                os.kill(children['cdr_tcp_bridge'], signal.SIGINT)
                wait_for(lambda: '[cdr_tcp_bridge-1]: process has finished cleanly' in logfile.read_text(),
                         process, 'bridge exits')
                before = len(commands)
                pump(.5)
                assert process.poll() is None, 'bridge exit stopped launch'
                assert len(commands) > before, 'bridge exit stopped command publication'
                os.kill(children['encoder_node'], 0)
                print('PASS bridge: client disconnect and server exit leave control running', flush=True)
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=6.)
                assert process.returncode == 0, 'unclean launch shutdown'
                for pid in children.values():
                    assert not Path('/proc', str(pid)).exists(), 'launch left a child alive'
                print('PASS launch: Ctrl-C stops remaining children cleanly', flush=True)
            finally:
                stop_process(process)
    finally:
        for subscription in subscriptions:
            node.destroy_subscription(subscription)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
