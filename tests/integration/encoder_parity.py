"""Run the real CUDA encoder against a fixed native-resolution TCP image."""
import os
import argparse
import hashlib
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time

import cv2
import numpy as np
import onnxruntime as ort
import rclpy
from sensor_msgs.msg import Image
from vision_encoders.msg import ImageTokens

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model-path', type=Path, required=True)
parser.add_argument('--node-path', type=Path, required=True)
parser.add_argument('--log-dir', type=Path, required=True)
args = parser.parse_args()
args.log_dir.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(93)
frames = [rng.integers(0, 256, (63, 112, 3), dtype=np.uint8) for _ in range(8)]
records = []
for frame in frames:
    ok, png = cv2.imencode('.png', frame)
    assert ok
    records.append(struct.pack('<I', len(png)) + png.tobytes())
expected_hashes = {hashlib.sha256(frame.tobytes()).hexdigest(): frame for frame in frames}
server = socket.socket()
server.bind(('127.0.0.1', 0))
server.listen(1)
server.settimeout(30)
stop = threading.Event()

def stream():
    try:
        conn, _ = server.accept()
        with conn:
            count = 0
            while not stop.wait(0.05):
                conn.sendall(records[count % len(records)])
                count += 1
    except (OSError, TimeoutError):
        pass

thread = threading.Thread(target=stream, daemon=True)
thread.start()
rclpy.init()
node = rclpy.create_node('parity_test')
images, tokens = [], []
node.create_subscription(Image, '/parity/frame', images.append, 1)
node.create_subscription(ImageTokens, '/parity/tokens', tokens.append, 1)
with (args.log_dir / 'encoder_node.log').open('w') as log:
    process = subprocess.Popen([
        str(args.node_path),
        '--ros-args', '-p', 'model_path:=' + str(args.model_path),
        '-p', 'camera_port:=' + str(server.getsockname()[1]),
        '-p', 'frame_topic:=/parity/frame', '-p', 'tokens_topic:=/parity/tokens'],
        stdout=log, stderr=subprocess.STDOUT)
    try:
        def stamp(message):
            return (message.header.stamp.sec, message.header.stamp.nanosec)

        matched = {}
        deadline = time.monotonic() + 35
        while len(matched) < len(frames) and time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('encoder exited; inspect encoder_node.log')
            rclpy.spin_once(node, timeout_sec=0.1)
            by_stamp = {stamp(token): token for token in tokens}
            for img in images:
                if stamp(img) not in by_stamp:
                    continue
                actual = np.asarray(img.data, dtype=np.uint8).reshape(img.height, img.width, 3)
                digest = hashlib.sha256(actual.tobytes()).hexdigest()
                assert digest in expected_hashes, 'native pixels were resampled'
                matched[digest] = by_stamp[stamp(img)]
        assert len(matched) == len(frames), 'missing synchronized frame/token pairs'
        print('PASS: all 8 native TCP PNG frames preserve model-input pixels exactly')
        session = ort.InferenceSession(str(args.model_path), providers=['CPUExecutionProvider'])
        worst = [0.0, 0.0]
        for digest, token in matched.items():
            expected = session.run(None, {'image_bgr_hwc': expected_hashes[digest][None]})
            actual = (np.asarray(token.patches, dtype=np.float32).reshape(1, 21, 192),
                      np.asarray(token.cls, dtype=np.float32).reshape(1, 192))
            errors = [float(np.max(np.abs(a - b))) for a, b in zip(actual, expected)]
            assert max(errors) <= 1e-4, errors
            worst = [max(a, b) for a, b in zip(worst, errors)]
        print('PASS: CPU vs CUDA errors over 8 frames (patches, CLS):', worst)
    finally:
        stop.set()
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        server.close()
        node.destroy_node()
        rclpy.shutdown()
