#!/usr/bin/env python3
#
# Init order (critical — three-way CUDA/DDS/GLib conflict):
#   1. TRT warmup        → establishes CUDA context
#   2. rclpy.init()      → starts ROS2 DDS (safe after CUDA is up)
#   3. Node.__init__()   → creates ROS2 node
#   4. import gi.Gst     → GLib bindings must come AFTER both CUDA + DDS
#   5. Gst.init(None)    → start GStreamer pipeline
#
# Importing gi.repository.Gst at the top-level crashes TRT or Node creation.
import os
import yaml
import cv2
import numpy as np
from ultralytics import YOLO

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from cv_bridge import CvBridge

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../configs/drone.yaml")
WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "../weights")


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


class DetectionNode(Node):
    def __init__(self, model: YOLO):
        super().__init__("detection_node")

        # Import GStreamer AFTER super().__init__() — GLib/DDS conflict fix
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        self.Gst = Gst

        self.model = model
        self.get_logger().info("YOLO model ready.")

        config = load_config(CONFIG_PATH)
        drone = config["drone"]
        rtsp_url = f"rtsp://{drone['ip']}:{drone['rtsp_port']}{drone['rtsp_path']}"

        Gst.init(None)
        self.get_logger().info(f"Connecting to {rtsp_url}")
        pipeline_str = (
            f"rtspsrc location={rtsp_url} protocols=tcp latency=0 "
            f"! decodebin ! videoconvert ! video/x-raw,format=BGR "
            f"! appsink name=sink drop=true sync=false"
        )
        self.pipeline_str = pipeline_str
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsink = self.pipeline.get_by_name("sink")
        self.bus = self.pipeline.get_bus()
        self.pipeline.set_state(Gst.State.PLAYING)

        self.bridge = CvBridge()
        self.image_pub = self.create_publisher(Image, "/drone/image_raw", 10)
        self.detection_pub = self.create_publisher(Detection2DArray, "/drone/detections", 10)
        self.overlay_pub = self.create_publisher(Image, "/drone/image_detections", 10)

        self.timer = self.create_timer(0.033, self.process_frame)

    def pull_frame(self):
        sample = self.appsink.emit("try-pull-sample", self.Gst.SECOND)
        if not sample:
            return None
        buf = sample.get_buffer()
        caps = sample.get_caps()
        struct = caps.get_structure(0)
        width = struct.get_value("width")
        height = struct.get_value("height")
        data = buf.extract_dup(0, buf.get_size())
        return np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))

    def restart_pipeline(self):
        self.get_logger().warn("Restarting GStreamer pipeline...")
        self.pipeline.set_state(self.Gst.State.NULL)
        self.pipeline = self.Gst.parse_launch(self.pipeline_str)
        self.appsink = self.pipeline.get_by_name("sink")
        self.bus = self.pipeline.get_bus()
        self.pipeline.set_state(self.Gst.State.PLAYING)
        self.get_logger().info("GStreamer pipeline restarted.")

    def process_frame(self):
        msg = self.bus.pop_filtered(self.Gst.MessageType.ERROR | self.Gst.MessageType.EOS)
        if msg:
            if msg.type == self.Gst.MessageType.ERROR:
                err, _ = msg.parse_error()
                self.get_logger().error(f"GStreamer error: {err.message}")
            else:
                self.get_logger().warn("GStreamer EOS received.")
            self.restart_pipeline()
            return

        frame = self.pull_frame()
        if frame is None:
            return

        stamp = self.get_clock().now().to_msg()

        img_msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        img_msg.header.stamp = stamp
        img_msg.header.frame_id = "drone_camera"
        self.image_pub.publish(img_msg)

        results = self.model(frame, verbose=False)[0]

        det_array = Detection2DArray()
        det_array.header.stamp = stamp
        det_array.header.frame_id = "drone_camera"

        for box in results.boxes:
            class_id = int(box.cls[0])
            label = self.model.names[class_id]
            if label != "person":
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            score = float(box.conf[0])

            det = Detection2D()
            det.header.stamp = stamp
            det.header.frame_id = "drone_camera"
            det.bbox.center.position.x = (x1 + x2) / 2.0
            det.bbox.center.position.y = (y1 + y2) / 2.0
            det.bbox.size_x = x2 - x1
            det.bbox.size_y = y2 - y1

            hyp = ObjectHypothesisWithPose()
            hyp.hypothesis.class_id = label
            hyp.hypothesis.score = score
            det.results.append(hyp)

            det_array.detections.append(det)

        self.detection_pub.publish(det_array)

        overlay = frame.copy()
        for det in det_array.detections:
            cx = det.bbox.center.position.x
            cy = det.bbox.center.position.y
            w = det.bbox.size_x
            h = det.bbox.size_y
            x1 = int(cx - w / 2)
            y1 = int(cy - h / 2)
            x2 = int(cx + w / 2)
            y2 = int(cy + h / 2)
            score = det.results[0].hypothesis.score
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(overlay, f"person {score:.2f}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        overlay_msg = self.bridge.cv2_to_imgmsg(overlay, encoding="bgr8")
        overlay_msg.header.stamp = stamp
        overlay_msg.header.frame_id = "drone_camera"
        self.overlay_pub.publish(overlay_msg)

    def destroy_node(self):
        self.pipeline.set_state(self.Gst.State.NULL)
        super().destroy_node()


def main():
    config = load_config(CONFIG_PATH)
    model_name = config.get("model", {}).get("name", "yolo11m")
    engine_path = os.path.join(WEIGHTS_DIR, f"{model_name}.engine")
    pt_path = os.path.join(WEIGHTS_DIR, f"{model_name}.pt")

    # Step 1: export engine if needed (BEFORE rclpy.init() and BEFORE gi.Gst import)
    if not os.path.exists(engine_path):
        print(f"[INFO] Exporting {pt_path} → {engine_path} ...")
        YOLO(pt_path).export(format="engine", device=0, simplify=True)
        print("[INFO] Export done.")

    # Step 2: load + warmup TRT BEFORE rclpy.init() (establishes CUDA context)
    print(f"[INFO] Pre-loading TRT engine: {engine_path}")
    model = YOLO(engine_path, task="detect")
    model(np.zeros((640, 640, 3), dtype=np.uint8), verbose=False)
    print("[INFO] TRT engine warmed up.")

    # Step 3: init ROS2 (AFTER CUDA is up, BEFORE gi.Gst import)
    rclpy.init()

    # Step 4: create node — gi.Gst is imported inside __init__ after super()
    node = DetectionNode(model=model)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
