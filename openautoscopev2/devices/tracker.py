#! python
#
# Copyright 2021
# Authors: Mahdi Torkashvand

"""
This creates a device for the auto tracker

Usage:
    tracker.py                   [options]

Options:
    -h --help                           Show this help.
    --commands_in=HOST:PORT             Host and Port for the incomming commands.
                                            [default: localhost:5001]
    --commands_out=HOST:PORT            Host and Port for the outgoing commands.
                                            [default: localhost:5000]
    --data_in=HOST:PORT                 Host and Port for the incomming image.
                                            [default: localhost:5005]
    --data_out=HOST:PORT                Host and Port for the outgoing image.
                                            [default: localhost:5005]
    --format=UINT8_YX_512_512           Size and type of image being sent.
                                            [default: UINT8_YX_512_512]
    --name=NAME                         Device Name.
                                            [default: tracker]
    --interpolation_tracking=BOOL       Uses user-specified points to interpolate z.
                                            [default: False]
    --data_out_debug=HOST:PORT                Host and Port for the outgoing debug image.
                                            [default: localhost:5009]
"""

# Modules
import time
import json
from typing import Tuple
import onnxruntime


import zmq
import cv2 as cv
import numpy as np
from docopt import docopt
from openautoscopev2.devices.pid_controller import PIDController
from openautoscopev2.devices.tracker_tools import (
    XYZ4xSharpness
)

from openautoscopev2.zmq.array import TimestampedSubscriber, TimestampedPublisher
from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.utils import parse_host_and_port
from openautoscopev2.devices.utils import array_props_from_string

## TrackerDevice
class TrackerDevice():
    """This creates a device that subscribes to images from a camera
    and sends commands to the motors"""

    def __init__(
            self,
            commands_in: Tuple[str, int, bool],
            commands_out: Tuple[str, int],
            data_in: Tuple[str, int, bool],
            data_out: Tuple[str, int],
            fmt: str,
            interpolation_tracking:bool,
            name: str,
            data_out_debug: Tuple[str, int] = None
        ):
        
        # Tracking Parameters
        ## Camera Related
        self.SMALLES_TRACKING_OBJECT = 200  # For Eggs to L1
        self.PIXEL_RATIO_WORM_MAX = 0.25
        self.TRACKEDWORM_SIZE_FLUCTUATIONS = 0.25
        self.TRACKEDWORM_CENTER_SPEED = 100
        self.missing_worm_idx = 0
        self.MISSING_WORM_TOLERANCE = 45
        ## Masking Worm
        self.MASK_WORM_THRESHOLD = 110
        self.MASK_WORM_THRESHOLD_BLURED = self.MASK_WORM_THRESHOLD*1.1
        self.MASK_MEDIAN_BLUR = 9
        self.MASK_KERNEL_BLUR = 5
        ## Sharpness Calculation
        self.SHRPNESS_SAMPLES = 30
        self.SHARPNESS_PADDING = 5
        self.SHARPNESS_MIN_LENGTH = 20
        # CAUTION: `interpolation_tracking` is passed as `str`
        self.interpolation_tracking = interpolation_tracking.lower() == 'true' if isinstance(interpolation_tracking, str) else interpolation_tracking
        self.are_points_set = False
        self.points = np.zeros((3, 3)) * np.nan
        self.curr_point = np.zeros(3)
        self.N = np.zeros(3) * np.nan
        self.isN = False
        self.offset_z = 0
        

        np.seterr(divide = 'ignore')
        self.status = {}
        self.data_out = data_out
        self.data_out_debug = data_out_debug
        self.data_in = data_in
        self.poller = zmq.Poller()
        self.name = name
        (self.dtype, _, self.shape) = array_props_from_string(fmt)  # UINT8_YX_512_512 -> dtype = uint8 , shape = (512,512)
        self.out = np.zeros(self.shape, dtype=self.dtype)
        self.data = np.zeros(self.shape)
        # y is the first index and x is the second index in the image
        self.detect = lambda img: img
        self.xyz4xsharpness = XYZ4xSharpness(tracker=self)
        self.y_worm = self.shape[0]//2
        self.x_worm = self.shape[1]//2
        self.pid_controller = PIDController(Kpy=15, Kpx=15, Kiy=0, Kix=0, Kdy=0, Kdx=0, SPy=self.shape[0]//2, SPx=self.shape[1]//2)

        ## Z Tracking
        self.shrp_idx = 0
        self.shrp_hist_size = 30
        self.shrp_hist = np.zeros(self.shrp_hist_size)  # TODO change value
        self.VZ_MAX = 8
        self.vz = self.VZ_MAX

        ## Tracked Worm Info
        self.trackedworm_size = None
        self.trackedworm_center = None
        self.found_trackedworm = False

        self.tracking = False
        self.running = True

        self.ort_session = None

        self.command_publisher = Publisher(
            host=commands_out[0],
            port=commands_out[1],
            bound=commands_out[2])
        
        self.data_publisher = TimestampedPublisher(
            host=self.data_out[0],
            port=self.data_out[1],
            bound=self.data_out[2],
            shape=self.shape,
            datatype=self.dtype)

        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=name,
            host=commands_in[0],
            port=commands_in[1],
            bound=commands_in[2])

        self.data_subscriber = TimestampedSubscriber(
            host=self.data_in[0],
            port=self.data_in[1],
            bound=self.data_in[2],
            shape=self.shape,
            datatype=self.dtype)

        self.poller.register(self.command_subscriber.socket, zmq.POLLIN)
        self.poller.register(self.data_subscriber.socket, zmq.POLLIN)

        time.sleep(1)
        self.publish_status()

    def set_point(self, i):
        self.command_publisher.send(f"teensy_commands get_pos {self.name} {i}")
        self.send_log(f"get_pos({self.name},{i}) request sent")

    def set_pos(self, i, x, y, z):
        idx = i % 3 - 1
        self.points[idx] = [x, y, z]
        self.send_log(f"set_pos called with i->idx: {i}->{idx}, pos ({x}, {y}, {z})")
        if not np.any(np.isnan(self.points)):
            # Surface Normal
            A = self.points[1] - self.points[0]
            B = self.points[1] - self.points[2]
            self.N = np.cross(A, B)
            self.N /= np.linalg.norm(self.N)
            if self.N[2] < 0 :
                self.N *= -1
            self.d0 = np.dot(self.N, self.points[0])
            self.isN = True
            # Surface Parameters
            self.send_log({
                "desc": "Surface Normal Parameters",
                "normal": str(self.N),
                "intercept": str(self.d0),
            })

    def estimate_vz_by_interpolation(self):
        if not self.isN:
            self.vz = 0
            return
        curr_point_offsetted = self.curr_point.copy()
        curr_point_offsetted[2] += self.offset_z
        d = np.dot(curr_point_offsetted, self.N) - self.d0
        sign = -np.sign(d)
        magnitude = (self.VZ_MAX * 2) * ( np.abs(d) / (1+np.abs(d)) )
        self.vz = int( sign * magnitude )

        

    def get_curr_pos(self):
        self.command_publisher.send(f"teensy_commands get_curr_pos {self.name}")
        self.send_log(f"get_curr_pos() request sent")

    def set_curr_pos(self, x, y, z):
        self.curr_point[:] = [x, y, z]
        self.send_log(f"received position ({x},{y},{z})")

    def set_offset_z(self, offset_z):
        self.offset_z = offset_z
        self.send_log(f"offset-z changed to {self.offset_z}")

    # Detectors
    def set_tracking_system(self, tracking_specs, fp_model_onnx):
        tracking_specs = tracking_specs.lower()
        if 'default' in tracking_specs:
            self.magnification, self.condition = "10x", "glass"
        else:
            self.magnification, self.condition = tracking_specs.split('_', 1)
        # 4x_plate
        if self.magnification == "4x":
            self.interpolation_tracking = False
            self.xyz4xsharpness.reset()
            self.detect = self.xyz_detection_4x
        # 10x_plate, 10x_glass
        elif self.magnification == "10x":
            self.ort_session = onnxruntime.InferenceSession(fp_model_onnx)
            if "glass" in self.condition:
                self.interpolation_tracking = True
                self.detect = self.xyz_detection_10x_glass
            elif "plate" in self.condition:
                self.interpolation_tracking = False
                self.detect = self.xyz_detection_10x_plate
            else:
                raise NotImplemented()
        return
    def xyz_detection_4x(self, img):
        img_annotated = self.xyz4xsharpness.detect(img)
        return img_annotated
    def xyz_detection_10x_glass(self, img):
        ################################################################################
        # Detect X-Y Coordinates
        self.found_trackedworm = True
        self.vz = None
        ## Detect using Model
        if self.ort_session is not None:
            img_cropped = img[56:-56,56:-56]
            batch_1_400_400 = {
                'input': np.repeat(
                    img_cropped[None, None, :, :], 3, 1
                ).astype(np.float32)
            }
            ort_outs = self.ort_session.run( None, batch_1_400_400 )
            self.y_worm, self.x_worm = ort_outs[0][0].astype(np.int64) + 56
        else:  # No ORT Session
            self.y_worm, self.x_worm = self.shape[0]//2, self.shape[1]//2

        # Visualize Informations
        img_annotated = img.copy()
        img_annotated = cv.circle(img_annotated, (int(self.y_worm), int(self.x_worm)), radius=10, color=255, thickness=2)
        img_annotated = cv.circle(img_annotated, (256, 256), radius=2, color=255, thickness=2)  # Center of image
        ################################################################################
        # Detect Z Velocity
        self.estimate_vz_by_interpolation()
        # Return
        return img_annotated
    def xyz_detection_10x_plate(self, img):
        ################################################################################
        # Detect X-Y Coordinates
        self.found_trackedworm = True
        self.vz = None
        ## Detect using Model
        if self.ort_session is not None:
            img_cropped = img[56:-56,56:-56]
            batch_1_400_400 = {
                'input': np.repeat(
                    img_cropped[None, None, :, :], 3, 1
                ).astype(np.float32)
            }
            ort_outs = self.ort_session.run( None, batch_1_400_400 )
            self.y_worm, self.x_worm = ort_outs[0][0].astype(np.int64) + 56
        else:  # No ORT Session
            self.y_worm, self.x_worm = self.shape[0]//2, self.shape[1]//2

        # Visualize Informations
        img_annotated = img.copy()
        img_annotated = cv.circle(img_annotated, (int(self.y_worm), int(self.x_worm)), radius=10, color=255, thickness=2)
        img_annotated = cv.circle(img_annotated, (256, 256), radius=2, color=255, thickness=2)  # Center of image
        ################################################################################
        # Detect Z Velocity
        self.vz = None
        return img_annotated

    def process(self):
        """This processes the incoming images and sends move commands to zaber."""
        # Get Image Data
        msg = self.data_subscriber.get_last()
        if msg is not None:
            self.data = msg[1]
        
        # Base Cases
        ## None Message
        if msg is None:
            return
        if self.name == "tracker_gcamp":
            self.data_publisher.send(self.data)
            return

        # Find Worm
        img = self.data

        # Track X-Y-Z
        img_annotated = self.detect(img)

        # Behavior Displayer
        self.data_publisher.send(img_annotated)


        # If no worm and tracking, stop moving to avoid collision
        if self.tracking and not self.found_trackedworm:
            # TODO why this happens that worm seems to be missing?!
            self.missing_worm_idx += 1
            # Interpolation Method
            self.vz = 0
            if self.interpolation_tracking:
                self.estimate_vz_by_interpolation()
            # Panic!!!!!
            if self.missing_worm_idx > self.MISSING_WORM_TOLERANCE:
                # TODO change it so when tracking is lost, we can help it manually. e.g. change camera position closer to worm and it continues to track
                if self.missing_worm_idx <= (self.MISSING_WORM_TOLERANCE+100):  # send command two times to ensure stopping of all motors
                    self.set_velocities(0, 0, 0)
                else:
                    self.set_velocities(None, None, None)
                if not self.interpolation_tracking:
                    self.print("TRACKING AND NO WORM!")
            return
        elif not self.found_trackedworm:
            return
        elif self.tracking and self.found_trackedworm:
            self.missing_worm_idx = 0

        # PID
        ## Velocities XY
        self.vy, self.vx = self.pid_controller.get_velocity(self.y_worm, self.x_worm)

        # Set Velocities
        if self.tracking:
            ## setting PID parameters
            self.set_velocities(-self.vy, self.vx, self.vz)

        # Return
        return


    def change(self, value):
        value_new = self.xytracker.DEVIATION_RATIO_THRESHOLD + float(value)
        self.xytracker.DEVIATION_RATIO_THRESHOLD = min(
            max(value_new, 0.0),
            1.0
        )

    def change_threshold(self, direction):
        _tmp = self.MASK_WORM_THRESHOLD
        self.MASK_WORM_THRESHOLD = np.clip(
            self.MASK_WORM_THRESHOLD + direction,
            0, 255
        )
        self.MASK_WORM_THRESHOLD_BLURED = self.MASK_WORM_THRESHOLD*1.1
        self.send_log(f"threshold changed {_tmp}->{self.MASK_WORM_THRESHOLD}")


    def start(self):
        if not self.tracking:
            self.shrp_idx = 0
            self.send_log("starting tracking")
        self.missing_worm_idx = 0
        self.trackedworm_center = None
        self.trackedworm_size = None
        self.tracking = True
        self.pid_controller.reset()

    def stop(self):
        if self.tracking:
            self.set_velocities(0, 0, 0)
            self.send_log("stopping tracking")
        self.missing_worm_idx = 0
        self.trackedworm_center = None
        self.trackedworm_size = None
        self.tracking = False
        self.pid_controller.reset()

    def shutdown(self):
        """Shutdown the tracking device."""
        self.send_log("shutdown command received")
        self.stop()
        self.running = False
        self.publish_status()

    def update_status(self):
        """updates the status dictionary."""
        self.status["shape"] = self.shape
        self.status["tracking"] = self.tracking
        self.status["device"] = self.running
        self.send_log("status update received")
        self.send_log(self.status)

    def send_log(self, msg_obj):
        """Send log data to logger device."""
        # Cases to Handle
        msg = str(msg_obj)
        if isinstance(msg_obj, dict):  # Dict/JSON
            msg = json.dumps(msg_obj, default=int)
        # Send log
        msg = "{} {} {}".format( time.time(), self.name, msg )
        self.command_publisher.send(f"logger {msg}")
        return
    
    def interpolate_z_tracking(self, yes_no):
        if isinstance(yes_no, bool):
            self.interpolation_tracking = yes_no
        elif isinstance(yes_no, int):
            self.interpolation_tracking = yes_no == 1
        else:
            self.interpolation_tracking = yes_no.lower() == 'true'


    def publish_status(self):
        """Publishes the status to the hub and logger."""
        self.update_status()
        self.command_publisher.send("hub " + json.dumps({self.name: self.status}, default=int))
        self.send_log({
            self.name: self.status
        })

    def run(self):
        """This subscribes to images and adds time stamp
         and publish them with TimeStampedPublisher."""

        while self.running:

            sockets = dict(self.poller.poll())

            if self.command_subscriber.socket in sockets:
                self.command_subscriber.handle()

            elif self.data_subscriber.socket in sockets:
                # Process
                self.process()
    # Print
    def print(self, msg):
        print(f"<{self.name}>@ {msg}")
        return

    # Set Velocities
    def set_velocities(self, vx, vy, vz):
        if vx is not None:
            self.command_publisher.send("teensy_commands movex {}".format(vx))
        if vy is not None:
            self.command_publisher.send("teensy_commands movey {}".format(vy))
        if vz is not None:
            self.command_publisher.send("teensy_commands movez {}".format(vz))
        self.send_log(f"set velocities ({vx},{vy},{vz})")
        self.get_curr_pos()
        return

    

def main():
    """Create and start auto tracker device."""

    arguments = docopt(__doc__)
    device = TrackerDevice(
        commands_in=parse_host_and_port(arguments["--commands_in"]),
        data_in=parse_host_and_port(arguments["--data_in"]),
        commands_out=parse_host_and_port(arguments["--commands_out"]),
        data_out=parse_host_and_port(arguments["--data_out"]),
        fmt=arguments["--format"],
        interpolation_tracking=arguments["--interpolation_tracking"],
        name=arguments["--name"],
        data_out_debug=parse_host_and_port(arguments["--data_out_debug"]),)

    device.run()

if __name__ == "__main__":
    main()
