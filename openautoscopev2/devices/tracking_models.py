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
import time

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

        # Run parameters
        self.tracking = True  # if tracking is active  DEBUG! IT WAS `FALSE`
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

    def detect(self, img):
        # Z focus
        # print(f"DEBUG sending z-worm-focus: {z_worm_focus}")
        if self.selected_focus_mode is None or self.selected_focus_mode == "" or self.selected_focus_mode == "none":
            self.z_worm_focus = None
        else:
            model_key = f"focus_{self.selected_focus_mode}"
            z_focus_sign = float(self.models_json[model_key]['sign'])
            ort_runtime = self.ort_dict[model_key]
            z_worm_focus = self.z_focus_single_channel_full_image(img, ort_runtime, sign=z_focus_sign)
            self.send_z_worm_focus( z_worm_focus )
            

        # XY tracking
        if self.selected_tracking_mode is None or self.selected_tracking_mode == "" or self.selected_tracking_mode == "none":
            self.x_worm, self.y_worm = None, None
        else:
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
        self.tracking = True
        return

    def stop_tracking(self):
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
        print(f"DEBUG focus mode set! {self.selected_focus_mode}")
        return

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
            elif self.tracking and self.data_subscriber.socket in sockets:  # images received for tracking
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
