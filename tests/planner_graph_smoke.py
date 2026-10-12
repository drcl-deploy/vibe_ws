#!/usr/bin/env python3
"""Isolated ROS contract check; never launches a controller or publishes joystick input."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def main():
    # Separate from simulation domain 1 and robot domain 0, on loopback only.
    os.environ['ROS_DOMAIN_ID'] = '93'
    os.environ['CYCLONEDDS_URI'] = '<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="lo" /></Interfaces></General></Domain></CycloneDDS>'
    os.environ['RMW_IMPLEMENTATION'] = 'rmw_cyclonedds_cpp'
    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from cpp_control.msg import ControllerStatus, MotionReference
    from unitree_hg.msg import LowState
    import yaml
    from planner_supervisor import stop_process

    rclpy.init()
    node = rclpy.create_node('sledgehammer_contract_test')
    state_pub = node.create_publisher(LowState, '/lowstate', 10)
    status_pub = node.create_publisher(ControllerStatus, '/vibe/controller/status',
                                       QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
    references = []
    sub = node.create_subscription(MotionReference, '/tracker/reference', references.append, 10)
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

    planner = supervisor = None
    with tempfile.TemporaryDirectory(prefix='vibe-graph-') as directory:
        folder = Path(directory)
        config = yaml.safe_load((ROOT / 'cyclonedds_ws/src/sledgehammer/config/repose_planner/g1_sim_v9_3.yaml').read_text())
        config['camera']['port'] = 59993  # no dependency on a running camera
        (folder / 'planner.yaml').write_text(yaml.safe_dump(config))
        with (folder / 'planner.log').open('w') as log, (folder / 'supervisor.log').open('w') as slog:
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

                marker = folder / 'dummy-started'
                child_code = 'from pathlib import Path; import time; Path(' + repr(str(marker)) + ').touch(); time.sleep(60)'
                supervisor_code = ('import sys; sys.path.insert(0, ' + repr(str(ROOT / 'scripts')) + '); '
                                   'from planner_supervisor import supervise; '
                                   'sys.exit(supervise(' + repr([sys.executable, '-c', child_code]) + '))')
                supervisor = subprocess.Popen([sys.executable, '-c', supervisor_code],
                                               stdout=slog, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 10
                while not marker.exists() and time.monotonic() < deadline:
                    pump(0.1)
                assert marker.exists(), 'Supervisor did not start its child after planner heartbeat'
                stop_process(planner)
                planner = None
                assert supervisor.wait(timeout=12) == 1, 'Planner loss did not stop the supervised launch'
                print('PASS: planner disconnect shuts down the supervised process', flush=True)
            except BaseException:
                print((folder / 'planner.log').read_text()[-5000:])
                print((folder / 'supervisor.log').read_text()[-3000:])
                raise
            finally:
                for process in [supervisor, planner]:
                    if process is not None:
                        stop_process(process)
    node.destroy_subscription(sub)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
