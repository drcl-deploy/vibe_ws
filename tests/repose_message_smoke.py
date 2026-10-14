#!/usr/bin/env python3
"""Check installed message ownership and read pre-migration bag data without ROS nodes."""

import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from rclpy.serialization import deserialize_message, serialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.utilities import get_message
import rosbag2_py
from sensor_msgs.msg import CameraInfo, CompressedImage, Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    import cpp_control.msg
    planner = Path(get_package_prefix('sledgehammer')) / 'lib/sledgehammer'
    sys.path.insert(0, str(planner))
    from repose_bag_types import bag_message
    # The calibration replay and validator must use the same compatibility resolver.
    import repose_replay_observe
    import repose_validate_observe_bag
    assert repose_replay_observe.bag_message is bag_message
    assert repose_validate_observe_bag.bag_message is bag_message
    viewer_path = Path(get_package_prefix('cpp_control')) / 'lib/cpp_control/replay_vibes.py'
    spec = importlib.util.spec_from_file_location('replay_vibes', viewer_path)
    viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(viewer)

    fixtures = json.loads((ROOT / 'tests/fixtures/legacy_repose_messages.json').read_text())
    for name, fixture in fixtures.items():
        assert not hasattr(cpp_control.msg, name), 'Stale cpp_control type still installed: ' + name
        schema = Path(get_package_share_directory('sledgehammer')) / 'msg' / (name + '.msg')
        assert hashlib.sha256(schema.read_bytes()).hexdigest() == fixture['schema_sha256'], name
        current = get_message('sledgehammer/msg/' + name)
        assert bag_message(fixture['old_type']) is current
        message = deserialize_message(base64.b64decode(fixture['cdr']), current)
        assert message_to_ordereddict(message) == fixture['fields'], name

    # An actual SQLite bag retains old type names and serialized bytes. Test the
    # installed replay reader, not just a generated-message import.
    with tempfile.TemporaryDirectory(prefix='legacy repose bag ') as temp:
        path = Path(temp) / 'bag'
        writer = rosbag2_py.SequentialWriter()
        writer.open(rosbag2_py.StorageOptions(uri=str(path), storage_id='sqlite3'),
                    rosbag2_py.ConverterOptions('cdr', 'cdr'))

        def write(topic, type_name, data, index):
            fields = dict(name=topic, type=type_name, serialization_format='cdr')
            try:
                metadata = rosbag2_py.TopicMetadata(id=index + 1, **fields)
            except TypeError:  # Humble/Foxy do not have the id constructor argument.
                metadata = rosbag2_py.TopicMetadata(**fields)
            writer.create_topic(metadata)
            writer.write(topic, data, 1_000_000_000 + index)

        topics = {'PlannerStatus': viewer.PLANNER_TOPIC,
                  'CubeObservation': repose_replay_observe.OBSERVATION_TOPIC,
                  'CalibrationState': repose_replay_observe.STATE_TOPIC}
        for index, (name, fixture) in enumerate(fixtures.items()):
            write(topics[name], fixture['old_type'], base64.b64decode(fixture['cdr']), index)
        header = deserialize_message(base64.b64decode(fixtures['CubeObservation']['cdr']),
                                     bag_message(fixtures['CubeObservation']['old_type'])).header
        for index, (topic, cls) in enumerate([
                (repose_replay_observe.COLOR_TOPIC, CompressedImage),
                (repose_replay_observe.DEPTH_TOPIC, Image),
                (repose_replay_observe.LABELS_TOPIC, Image),
                (repose_replay_observe.CAMERA_INFO_TOPIC, CameraInfo)], 3):
            message = cls(header=header)
            write(topic, 'sensor_msgs/msg/' + cls.__name__, serialize_message(message), index)
        del writer

        bag = viewer.BagAccess(path)
        reader = bag.open_reader()
        while reader.has_next():
            topic, serialized, _ = reader.read_next()
            names = {topic: name for name, topic in topics.items()}
            if topic not in names:
                continue
            name = names[topic]
            fixture = fixtures[name]
            cls = (bag.message_class(topic) if name == 'PlannerStatus'
                   else bag_message(bag.topic_types[topic]))
            assert message_to_ordereddict(deserialize_message(serialized, cls)) == fixture['fields']
        calibration = repose_replay_observe.CalibrationBag(path)
        assert len(calibration.samples) == 1
        sample = calibration.samples[0]
        assert message_to_ordereddict(sample['observation']) == fixtures['CubeObservation']['fields']
        assert message_to_ordereddict(sample['state']) == fixtures['CalibrationState']['fields']
    print('PASS: three planner-owned messages, unchanged CDR fields, and legacy bag replay')


if __name__ == '__main__':
    main()
