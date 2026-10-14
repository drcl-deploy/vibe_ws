#!/usr/bin/env python3
"""Isolated ROS contract check; no joystick input and no physical robot connection."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def stop_process(child):
    for sig, timeout in [(signal.SIGINT, 5), (signal.SIGTERM, 3), (signal.SIGKILL, 2)]:
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            break



def main():
    # Separate from simulation domain 1 and robot domain 0, on loopback only.
    os.environ['ROS_DOMAIN_ID'] = '93'
    os.environ['CYCLONEDDS_URI'] = '<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="lo" /></Interfaces></General></Domain></CycloneDDS>'
    os.environ['RMW_IMPLEMENTATION'] = 'rmw_cyclonedds_cpp'
    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from cpp_control.msg import ControllerStatus, MotionReference
    from sledgehammer.msg import PlannerStatus
    from std_msgs.msg import Empty
    from unitree_hg.msg import LowState
    import yaml

    rclpy.init()
    node = rclpy.create_node('sledgehammer_contract_test')
    state_pub = node.create_publisher(LowState, '/lowstate', 10)
    status_pub = node.create_publisher(ControllerStatus, '/vibe/controller/status',
                                       QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
    references = []
    sub = node.create_subscription(MotionReference, '/tracker/reference', references.append, 10)
    heartbeats = []
    node.create_subscription(Empty, '/vibe/planner/heartbeat', heartbeats.append,
                             QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
    state = LowState()
    state.imu_state.quaternion = [1., 0., 0., 0.]
    status = ControllerStatus()
    status.control_mode = ControllerStatus.POLICY
    status.default_joint_pos = [0.1] + [0.] * 28
    status.accepting = False
    status.finished = True

    def pump(seconds, send_status=True, send_state=True):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            if send_state:
                state_pub.publish(state)
            if send_status:
                status_pub.publish(status)
            rclpy.spin_once(node, timeout_sec=0.04)

    planner = tracker = None
    with tempfile.TemporaryDirectory(prefix='vibe-graph-') as directory:
        folder = Path(directory)
        config = yaml.safe_load((ROOT / 'cyclonedds_ws/src/sledgehammer/config/repose_planner/g1_sim_v9_3.yaml').read_text())
        config['camera']['port'] = 59993  # no dependency on a running camera
        (folder / 'planner.yaml').write_text(yaml.safe_dump(config))
        with (folder / 'planner.log').open('w') as log, (folder / 'tracker.log').open('w') as tlog:
            try:
                planner = subprocess.Popen([
                    'ros2', 'run', 'sledgehammer', 'g1_repose_planner_node', '--ros-args',
                    '-p', 'config_path:=' + str(folder / 'planner.yaml')],
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 10
                while status_pub.get_subscription_count() == 0 and time.monotonic() < deadline:
                    assert planner.poll() is None, 'Planner failed to start'
                    pump(0.1)
                assert status_pub.get_subscription_count() > 0, 'ControllerStatus QoS incompatible'
                pump(0.5)
                assert not references, 'Disarmed planner sent a reference'
                assert heartbeats, 'Disarmed planner did not publish its standard heartbeat'
                status.accepting = True
                pump(0.8)
                assert references, 'Fresh accepting controller did not receive a reference'
                print('PASS: controller/reference QoS and disarmed/armed gates', flush=True)

                pump(1.3, send_status=False)
                count = len(references)
                pump(0.7, send_status=False)
                assert len(references) == count, 'References continued after controller disconnect'
                status.accepting = False
                pump(0.6)
                assert len(references) == count, 'Disarmed reconnect resumed references'
                status.accepting = True
                pump(0.6)
                assert len(references) > count, 'Explicit accepting reconnect failed'
                print('PASS: controller disconnect stops references; disarmed reconnect stays idle', flush=True)

                pump(1.3, send_state=False)
                count = len(references)
                pump(0.7, send_state=False)
                assert len(references) == count, 'References continued without lowstate'
                print('PASS: lowstate disconnect stops references', flush=True)

                # The remaining check uses the actual direct launch. Remove the
                # test publishers before starting control; no state/joy is supplied.
                node.destroy_publisher(state_pub)
                node.destroy_publisher(status_pub)
                tracker = subprocess.Popen([
                    'ros2', 'launch', 'cpp_control', 'g1_vibe_sonic.launch.py',
                    'policy_path:=' + str(ROOT / 'artifacts/models/repose/policy.onnx'),
                    'encoder_path:=' + str(ROOT / 'artifacts/encoders/theia-tiny.onnx'),
                    'planner:=true', 'goal_color:=4', 'enable_bridge:=false',
                    'stand_yaw_teleop:=true', 'stand_walk_teleop:=true',
                    'stand_walk_motion:=' + str(ROOT / 'cyclonedds_ws/install/sledgehammer/share/sledgehammer/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz')],
                    stdout=tlog, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 30
                while node.count_subscribers('/vibe/planner/heartbeat') < 2 and time.monotonic() < deadline:
                    assert tracker.poll() is None, 'Direct tracker launch failed at startup'
                    rclpy.spin_once(node, timeout_sec=0.1)
                assert node.count_subscribers('/vibe/planner/heartbeat') >= 2, 'Native heartbeat subscription missing'
                assert node.count_subscribers('/vibe/planner/status') == 0, 'Tracker still depends on Repose status'
                until = time.monotonic() + 1.5
                while time.monotonic() < until:
                    rclpy.spin_once(node, timeout_sec=0.1)
                    assert tracker.poll() is None, 'Healthy planner did not keep tracker alive'
                stop_process(planner)
                planner = None
                # Detailed telemetry is not liveness: stale/replayed status must
                # not keep the controller alive after its planner stops ticking.
                noise = node.create_publisher(PlannerStatus, '/vibe/planner/status', 10)
                until = time.monotonic() + 3
                while tracker.poll() is None and time.monotonic() < until:
                    noise.publish(PlannerStatus())
                    rclpy.spin_once(node, timeout_sec=0.05)
                tracker.wait(timeout=15)
                text = (folder / 'tracker.log').read_text()
                assert 'planner heartbeat lost' in text, 'Native tracker did not report planner loss'
                assert 'encoder_node' in text and 'process has finished cleanly' in text, text[-2500:]
                deadline = time.monotonic() + 5
                while node.count_publishers('/enc/tokens') and time.monotonic() < deadline:
                    rclpy.spin_once(node, timeout_sec=0.1)
                assert node.count_publishers('/enc/tokens') == 0, 'Encoder survived direct launch shutdown'
                print('PASS: heartbeat loss stops tracker/encoder despite continuing Repose status', flush=True)
            except BaseException:
                print((folder / 'planner.log').read_text()[-5000:])
                print((folder / 'tracker.log').read_text()[-3000:])
                raise
            finally:
                for process in [tracker, planner]:
                    if process is not None:
                        stop_process(process)
    node.destroy_subscription(sub)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
