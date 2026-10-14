#!/usr/bin/env python3
"""Exercise the real planner launch in a PTY; isolated DDS, no control/joy inputs."""

import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import termios
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.environ['ROS_DOMAIN_ID'] = '94'
    os.environ['RMW_IMPLEMENTATION'] = 'rmw_cyclonedds_cpp'
    os.environ['CYCLONEDDS_URI'] = (
        '<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="lo" />'
        '</Interfaces></General></Domain></CycloneDDS>')
    import rclpy
    from sledgehammer.msg import PlannerStatus
    from std_msgs.msg import Int32

    # sim and real select their shipped YAML; camera is loopback only, with no
    # lowstate/controller publisher, so neither case can command a robot.
    for environment, stop_key in [('sim', b'q'), ('real', b'\x03')]:
        master, slave = pty.openpty()
        saved = termios.tcgetattr(slave)

        def child_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        process = subprocess.Popen([
            'ros2', 'launch', 'sledgehammer', 'planner.launch.py',
            'env:=' + environment, 'camera_ip:=127.0.0.1'],
            stdin=slave, stdout=slave, stderr=slave, preexec_fn=child_terminal)
        rclpy.init()
        node = rclpy.create_node('planner_console_test')
        goals, statuses = [], []
        node.create_subscription(Int32, '/vibe/sonic/goal_color', lambda m: goals.append(m.data), 10)
        node.create_subscription(PlannerStatus, '/vibe/planner/status', statuses.append, 10)
        transcript = bytearray()

        def pump():
            rclpy.spin_once(node, timeout_sec=0.02)
            while select.select([master], [], [], 0)[0]:
                try:
                    data = os.read(master, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not data:
                    break
                transcript.extend(data)

        def until(predicate, message, timeout=15):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                pump()
            assert predicate(), message

        try:
            until(lambda: b'\x1b[?1049h' in transcript and statuses,
                  'Default launch did not display console and publish planner status')
            assert statuses[-1].target_color == 4, 'Initial planner target differs'
            until(lambda: node.count_subscribers('/vibe/sonic/goal_color') >= 2,
                  'Goal subscribers not discovered')
            os.write(master, b'1')
            until(lambda: 1 in goals and statuses[-1].target_color == 1,
                  'Numeric color key did not reach planner/topic')
            os.write(master, b'p')
            until(lambda: 5 in goals and statuses[-1].target_color == 5,
                  'Named color key did not reach planner/topic')
            episode = statuses[-1].episode
            os.write(master, b'R')
            until(lambda: statuses[-1].episode > episode, 'R did not start a fresh trial')
            print(f'PASS {environment}: default same-terminal console, live numeric/name targets, R', flush=True)
            os.write(master, stop_key)
            until(lambda: process.poll() is not None, 'Console quit left launch running')
            until(lambda: node.count_publishers('/vibe/planner/status') == 0,
                  'Planner survived console/launch shutdown')
            pump()
            assert termios.tcgetattr(slave) == saved, 'Terminal mode was not restored'
            assert b'\x1b[?25h\x1b[?1049l' in transcript, 'Cursor/screen not restored'
            assert b'Traceback' not in transcript, transcript[-3000:].decode(errors='replace')
            print(f'PASS {environment}: {stop_key!r} stops planner and restores terminal', flush=True)
        except BaseException:
            Path('/tmp/planner-console-failed-transcript.log').write_bytes(transcript)
            print('Observed goals:', goals)
            print(transcript[-6000:].decode(errors='replace'))
            raise
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
            os.close(master)
            os.close(slave)
            node.destroy_node()
            rclpy.shutdown()

    # Automation can explicitly omit the console even with no terminal.
    process = subprocess.Popen([
        'ros2', 'launch', 'sledgehammer', 'planner.launch.py',
        'env:=sim', 'console:=false', 'camera_ip:=127.0.0.1'],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True)
    rclpy.init()
    node = rclpy.create_node('planner_headless_test')
    try:
        deadline = time.monotonic() + 15
        while node.count_publishers('/vibe/planner/status') == 0 and time.monotonic() < deadline:
            assert process.poll() is None, 'Headless planner exited'
            rclpy.spin_once(node, timeout_sec=0.1)
        assert node.count_publishers('/vibe/planner/status') > 0
        assert node.count_publishers('/vibe/sonic/goal_color') == 0
        print('PASS console:=false: planner starts without terminal/console', flush=True)
    finally:
        os.killpg(process.pid, signal.SIGINT)
        output, _ = process.communicate(timeout=10)
        node.destroy_node()
        rclpy.shutdown()
        assert b'repose_console.py' not in output, output.decode(errors='replace')


if __name__ == '__main__':
    main()
