# Copyright 2025
# Authors: Sina Rasouli, Mahdi Torkashvand

"""
This creates a device for the auto tracker

Usage:
    tracking_models.py                   [options]

Options:
    -h --help                           Show this help.
    --commands_in=HOST:PORT             Host and Port for the incomming commands.
                                            [default: localhost:5001]
    --commands_out=HOST:PORT            Host and Port for the outgoing commands.
                                            [default: localhost:5000]
    --data_in=HOST:PORT                 Host and Port for the incomming image.
                                            [default: localhost:5010]
    --name=NAME                         Device Name.
                                            [default: tracking_models]
    --gui_fp=DIR                        GUI directory used to load model names.
                                            [default: .]
"""

from docopt import docopt
from typing import Tuple
from openautoscopev2.zmq.utils import parse_host_and_port
import zmq
from openautoscopev2.zmq.array import TimestampedSubscriber
from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber



import numpy as np
import os
import json
import onnxruntime
import cv2 as cv
from skimage import filters
import time

# Threshold tracking parameters
XY_TRACKING_BLUR_SIZE = 5
XY_TRACKING_KERNEL_DILATE = np.ones((13,13))
XY_TRACKING_KERNEL_ERODE = np.ones((7,7))
XY_TRACKING_SMALLEST_TRACKING_OBJECT = 200
XY_TRACKING_SIZE_FLUCTUATIONS = 0.25
XY_TRACKING_CENTER_SPEED = 100
XY_TRACKING_MASK_KERNEL_BLUR = 5

def minmax(arr):
    return np.min(arr), np.max(arr)

def img_to_object_mask_threshold(img, threshold):
    img_blurred = cv.blur(img, (XY_TRACKING_BLUR_SIZE, XY_TRACKING_BLUR_SIZE))
    img_objects = (img_blurred < threshold).astype(np.float32)
    img_objects_eroded = cv.erode(img_objects, XY_TRACKING_KERNEL_ERODE).astype(np.float32)
    img_objects_dilated = cv.dilate(img_objects_eroded, XY_TRACKING_KERNEL_DILATE).astype(np.float32)
    _, labels, rectangles, _ = cv.connectedComponentsWithStats(img_objects_dilated.astype(np.uint8))
    for i, rectangle in enumerate(rectangles):
        _size = rectangle[-1]
        if _size <= XY_TRACKING_SMALLEST_TRACKING_OBJECT:
            indices = labels == i
            labels[indices] = 0
    mask = labels > 0
    return mask

# Hard coded parameters for data channel/connection between tracker and tracking_models
TRACKING_MODELS_IMAGE_SHAPE = (512, 512)
TRACKING_MODELS_DTYPE = np.uint8


class TrackingModels:

    def __init__(
            self,
            commands_in: Tuple[str, int, bool],
            commands_out: Tuple[str, int, bool],
            data_in: Tuple[str, int, bool],
            gui_fp: str,
            name: str = "oas_tracking_models"
        ):
        self.name = name
        self.gui_fp = gui_fp
        # Initial load
        self.models_json = dict()
        self.ort_dict = dict()
        self.selected_tracking_mode = None
        self.selected_focus_mode = None
        self.load_models()
        # Reporting prcessing time
        self.verbose_cycle_counter = 0
        self.verbose_total_time_XYtracker = 0.0
        self.verbose_total_time_autofocus = 0.0

        # Initialize all connections
        self.data = np.zeros(TRACKING_MODELS_IMAGE_SHAPE)

        # Tracking/Focusing parameters
        self.y_worm = None
        self.x_worm = None
        self.z_worm_focus = None
        self.trackedworm_size = None
        self.trackedworm_center = None

        # Run parameters
        self.tracking = False  # if tracking is active. only used by threshold xy tracking
        self.running = True  # if the process is running, e.g. listening for commands or waiting for images to process

        self.command_publisher = Publisher(
            host=commands_out[0],
            port=commands_out[1],
            bound=commands_out[2]
        )

        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=name,
            host=commands_in[0],
            port=commands_in[1],
            bound=commands_in[2]
        )

        self.data_subscriber = TimestampedSubscriber(
            host=data_in[0],
            port=data_in[1],
            bound=data_in[2],
            shape=TRACKING_MODELS_IMAGE_SHAPE,
            datatype=TRACKING_MODELS_DTYPE
        )

        self.poller = zmq.Poller()
        self.poller.register(self.command_subscriber.socket, zmq.POLLIN)
        self.poller.register(self.data_subscriber.socket, zmq.POLLIN)

        # Return
        return

    def load_models(self):
        # Load `models.json`
        fp_models_json = os.path.join(self.gui_fp, 'models.json')
        if not os.path.exists(fp_models_json):
            self._send_log( f"<TrackingModels> File does not exist! {fp_models_json}" )
            return
        ## Load models info
        with open(fp_models_json, "r") as in_file:
            self.models_json = json.load(in_file)
        ## Load ONNX sessions
        for model_key, entry in self.models_json.items():
            # Skip thresholding model
            if entry['path'].strip() == "":
                continue
            # Check model path
            fp_model = os.path.join(self.gui_fp, entry['path'])
            if not os.path.exists(fp_model):
                self._send_log( f"<TrackingModels> Model file does not exist! {fp_model}" )
                continue
            # Load inference runtime
            self.ort_dict[model_key] = onnxruntime.InferenceSession(fp_model)
        # Return
        return

    def send_z_worm_focus(self, z_worm_focus):
        self.command_publisher.send("tracker_behavior set_z_worm_focus {}".format( z_worm_focus ))
        return

    def send_xy_worm(self, x_worm, y_worm):
        self.command_publisher.send("tracker_behavior set_xy_worm {} {}".format( x_worm, y_worm ))
        return

    def send_boundingbox_worm(self, xmin, xmax, ymin, ymax):
        self.command_publisher.send("tracker_behavior set_boundingbox_worm {} {} {} {}".format( xmin, xmax, ymin, ymax ))
        return

    def detect(self, img):
        # Z focus
        if self.selected_focus_mode is None or self.selected_focus_mode == "" or self.selected_focus_mode == "none":
            self.z_worm_focus = None
        else:
            model_key = f"focus_{self.selected_focus_mode}"
            z_focus_sign = float(self.models_json[model_key]['sign'])
            ort_runtime = self.ort_dict[model_key]
            z_worm_focus = self.z_focus_single_channel_full_image(img, ort_runtime, sign=z_focus_sign)
            self.send_z_worm_focus( z_worm_focus )
            

        # XY tracking
        ## No tracking method
        if self.selected_tracking_mode is None or self.selected_tracking_mode == "" or self.selected_tracking_mode == "none":
            self.x_worm, self.y_worm = None, None
        elif self.selected_tracking_mode == "xy_threshold":  # Special case of XY-Thresholding method
            x_worm, y_worm, x_min, x_max, y_min, y_max = self.track_xy_using_threshold(img)
            self.send_xy_worm( x_worm, y_worm )
            self.send_boundingbox_worm( x_min, x_max, y_min, y_max )
        else:  # Using ML models (through ONNX runtime) for tracking
            model_key = f"tracking_{self.selected_tracking_mode}"
            ort_runtime = self.ort_dict[model_key]
            x_worm, y_worm = self.xy_tracking_single_channel_full_image(img, ort_runtime)
            self.send_xy_worm( x_worm, y_worm )

        # Reports
        self.verbose_cycle_counter += 1
        if self.verbose_cycle_counter%300 == 0:
            # Print to CMD
            print("Average inference XY/focus: {:>5.3f}/{:>5.3f} (ms)".format(
                1000*self.verbose_total_time_XYtracker/self.verbose_cycle_counter,
                1000*self.verbose_total_time_autofocus/self.verbose_cycle_counter
            ))
            # Reset
            self.verbose_cycle_counter = 0
            self.verbose_total_time_XYtracker = 0.0
            self.verbose_total_time_autofocus = 0.0

        # Return
        return

    def start_tracking(self):
        self.trackedworm_center = None
        self.trackedworm_size = None
        self.tracking = True
        return

    def stop_tracking(self):
        self.trackedworm_center = None
        self.trackedworm_size = None
        self.tracking = False
        return

    def set_tracking_mode(self, tracking_mode):
        self.selected_tracking_mode = tracking_mode
        if tracking_mode == "" or tracking_mode.lower() == "none":
            self.selected_tracking_mode = None
        return

    def set_focus_mode(self, focus_mode):
        self.selected_focus_mode = focus_mode
        if focus_mode == "" or focus_mode.lower() == "none":
            self.selected_focus_mode = None
        return

    def track_xy_using_threshold(self, img):
        # Image size for center finding
        ny, nx = img.shape[:2]
        # Threshold for distinguishing foreground and background
        otsu = filters.threshold_otsu(img)
        threshold = 1.2 * otsu if otsu > 50 else 110
        # Mask foreground objects
        img_mask_objects = img_to_object_mask_threshold(img, threshold=threshold)
        _ys, _xs = np.where(~img_mask_objects)
        _, labels, _, centroids = cv.connectedComponentsWithStats(
            img_mask_objects.astype(np.uint8)
        )
        # Find foreground candidates larger than a specific size
        centroids = centroids[:,::-1]  # swap i-j indices to match with `numpy.where` conventions
        labels_background = set(labels[_ys, _xs])
        label_values, label_counts = np.unique(labels.flatten(), return_counts=True)
        candidates_info = []
        for label_value, label_count, centroid in zip(label_values, label_counts, centroids):
            if label_value in labels_background:
                continue
            if label_count >= XY_TRACKING_SMALLEST_TRACKING_OBJECT:
                candidates_info.append([
                    labels == label_value,
                    centroid
                ])
        # Find closest candidate to center if the size is whithin a range of previous frame size
        found_trackedworm = False
        img_mask_trackedworm = None
        _d_center_closest = None
        if len(candidates_info) > 0:
            _center_previous = self.trackedworm_center \
                if self.tracking and self.trackedworm_center is not None else np.array([ny/2, nx/2])
            _size_lower = self.trackedworm_size*(1.0-XY_TRACKING_SIZE_FLUCTUATIONS) if self.tracking and self.trackedworm_size is not None else 0.0
            _size_upper = self.trackedworm_size*(1.0+XY_TRACKING_SIZE_FLUCTUATIONS) if self.tracking and self.trackedworm_size is not None else 0.0
            for _, (mask, center) in enumerate(candidates_info):
                _size = mask.sum()
                _d_center = np.max(np.abs(center - _center_previous))
                is_close_enough = _d_center <= XY_TRACKING_CENTER_SPEED
                if _size_upper != 0.0:
                    is_close_enough = is_close_enough and (_size_lower <= _size <= _size_upper)
                if is_close_enough:
                    found_trackedworm = True
                    if _d_center_closest is None or _d_center < _d_center_closest:
                        _d_center_closest = _d_center
                        img_mask_trackedworm = mask
                        if self.tracking:
                                self.trackedworm_size = _size
                                self.trackedworm_center = center.copy()
        # Send coords and bbox if worm was found
        y_min, y_max = None, None
        x_min, x_max = None, None
        self.x_worm, self.y_worm = None, None
        if found_trackedworm:
            img_mask_trackedworm_blurred = cv.blur(
                img_mask_trackedworm.astype(np.float32),
                (XY_TRACKING_MASK_KERNEL_BLUR, XY_TRACKING_MASK_KERNEL_BLUR)
            ) > 1e-4
            ys, xs = np.where(img_mask_trackedworm_blurred)
            y_min, y_max = minmax(ys)
            x_min, x_max = minmax(xs)
            self.x_worm = (x_min + x_max)//2
            self.y_worm = (y_min + y_max)//2
            self.is_xy_worm_set = True
        # Return the original image in case no worm detected
        return self.x_worm, self.y_worm, x_min, x_max, y_min, y_max

    def xy_tracking_single_channel_full_image(self, img, ort_runtime):
        batch_1_512_512 = {
            'input': img[np.newaxis, np.newaxis, :, :].astype(np.float32),
        }
        # The network is trained to output (x, y)
        _start = time.time()
        ort_outs = ort_runtime.run( None, batch_1_512_512 )
        self.x_worm, self.y_worm = ort_outs[0][0].astype(np.int64)
        _duration = time.time() - _start
        self.verbose_total_time_XYtracker += _duration
        # Return
        return self.x_worm, self.y_worm

    def z_focus_single_channel_full_image(self, img, ort_runtime, sign):
        # Network predicts z-focus
        batch_1_512_512 = {
            'input': img[np.newaxis, np.newaxis, :, :].astype(np.float32),
        }
        _start = time.time()
        ort_outs = ort_runtime.run( None, batch_1_512_512 )
        self.z_worm_focus = np.float32(ort_outs[0][0][0]) * sign
        _duration = time.time() - _start
        self.verbose_total_time_autofocus += _duration
        return self.z_worm_focus

    # Running loop
    def _run(self):
        while self.running:
            sockets = dict(self.poller.poll())
            # Listen for commands
            if self.command_subscriber.socket in sockets:
                self.command_subscriber.handle()
            elif self.data_subscriber.socket in sockets:  # images received for tracking
                # Get the image
                msg = self.data_subscriber.get_last()
                if msg is None:  # no new images received -> queue is empty
                    continue
                self.data = msg[1]  # only the image part
                self.detect( img = self.data )
        # Return
        return

    def shutdown(self):
        self._send_log("shutdown command received")
        self.tracking = False
        self.running = False
        return

    def _send_log(self, msg_obj):
        msg = str(msg_obj)
        if isinstance(msg_obj, dict):
            msg = json.dumps(msg_obj, default=int)

        msg = "{} {} {}".format( time.time(), self.name, msg )
        self.command_publisher.send(f"logger {msg}")
        return


# Entry point for CLI call
def main():

    arguments = docopt(__doc__)
    device = TrackingModels(
        commands_in=parse_host_and_port(arguments["--commands_in"]),
        commands_out=parse_host_and_port(arguments["--commands_out"]),
        data_in=parse_host_and_port(arguments["--data_in"]),
        gui_fp=arguments["--gui_fp"],
        name=arguments["--name"],
    )
    device._run()

if __name__ == "__main__":
    main()
