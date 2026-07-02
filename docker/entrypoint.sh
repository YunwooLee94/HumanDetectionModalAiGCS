#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

service ssh start

exec /bin/bash
