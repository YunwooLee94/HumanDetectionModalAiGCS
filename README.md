# Object Detection — Modal AI GCS

Real-time human detection from a drone RTSP stream using YOLO11 + TensorRT, published as ROS2 topics.

## Overview

| Topic | Type | Description |
|-------|------|-------------|
| `/drone/image_raw` | `sensor_msgs/Image` | Raw camera feed (uncompressed) |
| `/drone/image_raw/compressed` | `sensor_msgs/CompressedImage` | Raw camera feed — JPEG compressed, **lower latency over UDP** |
| `/drone/detections` | `vision_msgs/Detection2DArray` | Person bounding boxes |
| `/drone/image_detections` | `sensor_msgs/Image` | Camera feed with overlaid boxes (uncompressed) |
| `/drone/image_detections/compressed` | `sensor_msgs/CompressedImage` | Camera feed with overlaid boxes — JPEG compressed, **lower latency over UDP** |

> When viewing from a host computer via `rqt_image_view`, use the `/compressed` topics.
> They reduce data size ~15–20× (2.25 MB → ~120 KB per frame at JPEG quality 80),
> significantly cutting the UDP transport latency introduced by the Docker boundary.

## Quick Start

### 1. Configure the drone IP

Edit [`configs/drone.yaml`](configs/drone.yaml):

```yaml
drone:
  ip: 192.168.8.197   # <-- change this to your drone's IP
  rtsp_port: 8900
  rtsp_path: /live

model:
  name: yolo11m       # choices: yolo11n, yolo11s, yolo11m, yolo11l, yolo11x
```

### 2. Add model weights

Place the YOLO11 `.pt` file in the `weights/` directory:

```
weights/yolo11m.pt
```

The TensorRT engine (`.engine`) is generated automatically on first run.

### 3. Build and start the container

```bash
cd docker/
docker compose build
docker compose up -d
```

### 4. (Optional) Set ROS_DOMAIN_ID

Edit [`docker/.bashrc`](docker/.bashrc) to match the domain ID used by the rest of your ROS2 network:

```bash
# docker/.bashrc
export ROS_DOMAIN_ID=0   # change to your domain ID
```

Rebuild and restart the container after changing this file:

```bash
cd docker/
docker compose build
docker compose up -d
```

### 5. Run the detection node

```bash
docker exec -it object_detection_modal_ai_gcs bash
python3 /workspace/scripts/detection_node.py
```

## Project Structure

```
.
├── configs/
│   └── drone.yaml          # Drone IP and model selection
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .bashrc
│   └── entrypoint.sh
├── scripts/
│   ├── detection_node.py   # Main ROS2 detection node
│   └── run_gstreamer_receiver.py
└── weights/                # Place .pt files here (auto-exports .engine)
```

## Dependencies

All dependencies are installed inside the Docker container:

- **CUDA 12.8** + **cuDNN**
- **TensorRT 10.15.1.29**
- **PyTorch 2.9.1+cu128**
- **Ultralytics 8.3.240** (YOLO11)
- **ROS2 Humble** (`sensor_msgs`, `vision_msgs`, `cv_bridge`)
- **GStreamer 1.0** (RTSP video ingestion)
- **jemalloc** (required to prevent heap corruption in Docker's multi-threaded environment)

The host machine requires:
- Docker with NVIDIA Container Toolkit
- NVIDIA GPU driver compatible with CUDA 12.8
- **ROS2 Humble** with the following packages:

```bash
sudo apt install ros-humble-image-transport-plugins
```

`image-transport-plugins` provides the compressed image subscriber plugin required by `rqt_image_view` to display `/compressed` topics. Without it, `rqt_image_view` will show the error:

```
Unable to load plugin for transport 'image_transport/compressed_sub'
```
