#!/usr/bin/env python3
"""Keep a separately launched tracker tied to the planner's process lifetime."""

import os
import signal
import subprocess
import time


def stop_process(child):
    """Allow ROS shutdown, then reap any remaining children in its process group."""
    for sig, timeout in [(signal.SIGINT, 5), (signal.SIGTERM, 3), (signal.SIGKILL, 2)]:
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
        # The launch parent can exit before its workers. Check the group as well.
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            break


def supervise(command, timeout=1.0, ready_callback=None):
    """Start after a V9.3 heartbeat; stop on loss without automatically restarting."""
    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from cpp_control.msg import PlannerStatus

    rclpy.init()
    node = rclpy.create_node('vibe_planner_supervisor')
    last = [None]

    def heartbeat(msg):
        if msg.version == 'v9.3':
            last[0] = time.monotonic()

    subscription = node.create_subscription(
        PlannerStatus, '/vibe/planner/status', heartbeat,
        QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                   durability=DurabilityPolicy.VOLATILE))
    child = None
    print('Waiting for the V9.3 planner in terminal 3…', flush=True)
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            if last[0] is None:
                continue
            if time.monotonic() - last[0] >= timeout:
                print('Planner heartbeat lost; shutting down the tracker launch.', flush=True)
                return 1
            if child is None:
                child = subprocess.Popen(command, start_new_session=True)
                if ready_callback:
                    ready_callback()
            if child.poll() is not None:
                return child.returncode
    except KeyboardInterrupt:
        return 130
    finally:
        if child is not None:
            stop_process(child)
        node.destroy_subscription(subscription)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 1
