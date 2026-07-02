ARG BASE_IMAGE=nvcr.io/nvidia/cuda:12.8.0-cudnn-devel-ubuntu22.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ── System packages ───────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    vim htop tmux curl wget git \
    build-essential cmake \
    python3-pip python3-dev \
    # GStreamer
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    python3-gst-1.0 \
    # X11 for display
    libgl1 libglib2.0-0 \
    openssh-server \
    # jemalloc: prevents heap corruption when GLib + FastRTPS + CUDA
    # allocate concurrently in Docker (glibc ptmalloc is not safe here)
    libjemalloc2 \
    && rm -rf /var/lib/apt/lists/*

# ── ROS2 Humble ───────────────────────────────────────────────────────────────
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
        http://packages.ros.org/ros2/ubuntu jammy main" \
        > /etc/apt/sources.list.d/ros2.list && \
    apt-get update && apt-get install -y \
        ros-humble-ros-base \
        ros-humble-vision-msgs \
        ros-humble-cv-bridge \
        ros-humble-sensor-msgs \
        ros-humble-rmw-cyclonedds-cpp \
        python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages ───────────────────────────────────────────────────────────
# CRITICAL: pin NumPy < 2.0 before everything else — cv_bridge is compiled
# against NumPy 1.x and breaks with NumPy 2.x (_ARRAY_API not found)
RUN pip3 install --upgrade pip && pip3 install "numpy>=1.21,<2.0"

RUN pip3 install \
    "torch==2.9.1" "torchvision==0.24.1" --index-url https://download.pytorch.org/whl/cu128

RUN pip3 install \
    "ultralytics==8.3.240" \
    "opencv-python==4.8.1.78" \
    "PyYAML" \
    "tensorrt==10.15.1.29" \
    "onnxruntime"

# Re-pin NumPy in case any of the above upgraded it
RUN pip3 install "numpy>=1.21,<2.0"

# ── SSH ───────────────────────────────────────────────────────────────────────
RUN mkdir /var/run/sshd && \
    echo 'root:password' | chpasswd && \
    sed -i 's/^#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
EXPOSE 22

# ── ROS2 environment ──────────────────────────────────────────────────────────
# For interactive shells (docker exec ... bash)
RUN echo "source /opt/ros/humble/setup.bash" >> /etc/bash.bashrc

# For non-interactive shells (docker exec ... python3 script.py)
ENV ROS_DISTRO=humble \
    ROS_VERSION=2 \
    ROS_PYTHON_VERSION=3 \
    AMENT_PREFIX_PATH=/opt/ros/humble \
    COLCON_PREFIX_PATH=/opt/ros/humble \
    PATH=/opt/ros/humble/bin:$PATH \
    LD_LIBRARY_PATH=/opt/ros/humble/lib:$LD_LIBRARY_PATH \
    PYTHONPATH=/opt/ros/humble/lib/python3.10/site-packages:/opt/ros/humble/local/lib/python3.10/dist-packages

# ── Bashrc ────────────────────────────────────────────────────────────────────
COPY .bashrc /root/.bashrc

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

# ── Network utilities ─────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
