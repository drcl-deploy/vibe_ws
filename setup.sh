#!/bin/bash
echo "Setup unitree ros2 environment"
source /opt/ros/foxy/setup.bash
source $HOME/unitree_ros2/cyclonedds_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
unset ROS_LOCALHOST_ONLY
export VIBE_BRIDGE_ADDRESS=gilfoyle-rth
export VIBE_CAMERA_ADDRESS=127.0.0.1
export BRIDGE_ROS_DOMAIN_ID=71
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces>
                            <NetworkInterface name="enp3s0" priority="default" multicast="default" />
                        </Interfaces></General></Domain></CycloneDDS>'
