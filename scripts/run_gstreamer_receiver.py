#!/usr/bin/env python3
import subprocess
import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../configs/drone.yaml")


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    config = load_config(CONFIG_PATH)
    drone = config["drone"]
    rtsp_url = f"rtsp://{drone['ip']}:{drone['rtsp_port']}{drone['rtsp_path']}"

    cmd = [
        "gst-launch-1.0", "-v",
        "rtspsrc", f"location={rtsp_url}", "protocols=tcp", "latency=0",
        "!", "decodebin",
        "!", "videoconvert",
        "!", "autovideosink", "sync=true",
    ]

    print(f"Connecting to {rtsp_url}")
    print("Running:", " ".join(cmd))
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
