#!/usr/bin/env python3
"""Load each sample through the direct ROS launch, without state or joystick input."""

import json
import os
from pathlib import Path
import subprocess
import time

from planner_graph_smoke import stop_process

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = dict(os.environ, ROS_DOMAIN_ID='95', RMW_IMPLEMENTATION='rmw_cyclonedds_cpp',
               PYTHONDONTWRITEBYTECODE='1')
    env['CYCLONEDDS_URI'] = '<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="lo" /></Interfaces></General></Domain></CycloneDDS>'
    samples = json.loads((ROOT / 'data/sample/samples.json').read_text())['samples']
    artifacts = Path(env.get('VIBE_ARTIFACT_ROOT', ROOT / 'artifacts'))
    logs = ROOT / '.migration/samples-launch'
    logs.mkdir(parents=True, exist_ok=True)
    for name, spec in samples.items():
        logfile = logs / (name + '.log')
        command = ['ros2', 'launch', 'cpp_control', 'g1_vibe_sonic.launch.py',
                   'policy_path:=' + str(artifacts / spec['policy']),
                   'encoder_path:=' + str(artifacts / 'encoders/theia-tiny.onnx'),
                   'motion_path:=' + str(ROOT / 'data/sample' / name / 'motion.npz'),
                   'goal_color:=' + str(spec.get('goal_color', 0)),
                   'camera_ip:=192.0.2.1', 'enable_bridge:=false']
        with logfile.open('w') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                deadline = time.monotonic() + 40
                while time.monotonic() < deadline:
                    text = logfile.read_text()
                    if process.poll() is not None:
                        raise RuntimeError(name + ' exited during startup\n' + text[-5000:])
                    if 'g1_vibe ready:' in text and '21 patches x 192 dim' in text:
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError(name + ' did not become ready\n' + logfile.read_text()[-5000:])
                time.sleep(1)
                if process.poll() is not None:
                    raise RuntimeError(name + ' exited after startup\n' + logfile.read_text()[-5000:])
                print('PASS ' + name + ': reference, policy and encoder launch; no state/joy sent', flush=True)
            finally:
                stop_process(process)


if __name__ == '__main__':
    main()
