# Copyright 2023
# Authors: Mahdi Torkashvand, Sina Rasouli

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
    --data_out_displayer=HOST:PORT      Host and Port for the outgoing image to display.
                                            [default: localhost:5006]
    --data_out_writer=HOST:PORT         Host and Port for the outgoing image to save.
                                            [default: localhost:5007]
    --data_out_tracking_model=HOST:PORT Host and Port for the outgoing image to tracking model.
                                            [default: localhost:0]
    --format=UINT8_YX_512_512           Size and type of image being sent.
                                            [default: UINT8_YX_512_512]
    --name=NAME                         Device Name.
                                            [default: tracker]
    --interpolation_tracking=BOOL       Uses user-specified points to interpolate z.
                                            [default: False]
    --z_autofocus_tracking=BOOL       Uses a pre-trained model to estimate focus.
                                            [default: False]
    --gui_fp=DIR                        GUI directory used to load model names.
                                            [default: .]
    --flip_image                        Flip x in recieved image before publishing.
"""

import time
import json
from typing import Tuple


import zmq
import cv2 as cv
import numpy as np
from docopt import docopt
from openautoscopev2.devices.pid_controller import PIDController

from openautoscopev2.zmq.array import TimestampedPublisher, TimestampedSubscriber
from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.utils import parse_host_and_port
from openautoscopev2.devices.utils import array_props_from_string






def is_nan(x):
    return ( x is None or isinstance(x, str) or np.isnan(x) )


class TrackerDevice:

    def __init__(
            self,
            commands_in: Tuple[str, int, bool],
            commands_out: Tuple[str, int],
            data_in: Tuple[str, int, bool],
            data_out_writer: Tuple[str, int],
            data_out_displayer: Tuple[str, int],
            data_out_tracking_model: Tuple[str, int],
            fmt: str,
            interpolation_tracking:bool,
            z_autofocus_tracking:bool,
            name: str,
            gui_fp: str,
            flip_image: bool
        ):

        self.flip_image = flip_image

        self.missing_worm_idx = 0
        self.MISSING_WORM_TOLERANCE = 45
        self.VZ_MAX = 16

        self.TRACKING_RETRACTION_FACTOR_XY = 0.87  # 256*x^40 = 1 -> getting to sub 1 pixel close to image center after 40 frames
        self.TRACKING_RETRACTION_FACTOR_Z  = 0.93  # x^40 = 0.05 -> getting to sub 0.05 in terms of focus estimation after 40 frames

        self.interpolation_tracking = interpolation_tracking.lower() == 'true' if isinstance(interpolation_tracking, str) else interpolation_tracking
        self.z_autofocus_tracking = z_autofocus_tracking.lower() == 'true' if isinstance(z_autofocus_tracking, str) else z_autofocus_tracking
        self.points = np.zeros((3, 3)) * np.nan
        self.curr_point = np.zeros(3)
        self.N = np.zeros(3) * np.nan
        self.isN = False
        self.offset_z = 0
        

        np.seterr(divide = 'ignore')
        self.name = name
        (dtype, _, self.shape) = array_props_from_string(fmt)
        self.data = np.zeros(self.shape)
        self.img_y_center, self.img_x_center = 256, 256  # Hard-coded 512*512 displayer size and resizing before tracking

        self.tracking_mode = None
        self.focus_mode = None
        self.is_xy_worm_set = False
        self.is_z_worm_set = False
        self.y_worm = self.img_y_center
        self.x_worm = self.img_x_center
        self.bbox_worm_xmin, self.bbox_worm_xmax = None, None
        self.bbox_worm_ymin, self.bbox_worm_ymax = None, None
        self.z_worm_focus = None
        self.z_worm_focus_offset = 0.0
        self.pid_controller = PIDController(
            Kpy=10, Kpx=10, Kiy=0, Kix=0, Kdy=0, Kdx=0,
            SPy=self.img_y_center, SPx=self.img_x_center
        )
        self.verbose_z_focus_counter = 0

        self.found_trackedworm = False

        self.tracking = False
        self.running = True

        self.command_publisher = Publisher(
            host=commands_out[0],
            port=commands_out[1],
            bound=commands_out[2])
        
        self.data_publisher_writer = TimestampedPublisher(
            host=data_out_writer[0],
            port=data_out_writer[1],
            bound=data_out_writer[2],
            shape=self.shape,
            datatype=dtype)
        
        self.data_publisher_displayer = TimestampedPublisher(
            host=data_out_displayer[0],
            port=data_out_displayer[1],
            bound=data_out_displayer[2],
            shape=self.shape,
            datatype=dtype)

        self.data_publisher_tracking_models = TimestampedPublisher(
            host=data_out_tracking_model[0],
            port=data_out_tracking_model[1],
            bound=data_out_tracking_model[2],
            shape=self.shape,
            datatype=dtype
        ) if data_out_tracking_model is not None else None

        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=name,
            host=commands_in[0],
            port=commands_in[1],
            bound=commands_in[2])

        self.data_subscriber = TimestampedSubscriber(
            host=data_in[0],
            port=data_in[1],
            bound=data_in[2],
            shape=self.shape,
            datatype=dtype)

        self.poller = zmq.Poller()
        self.poller.register(self.command_subscriber.socket, zmq.POLLIN)
        self.poller.register(self.data_subscriber.socket, zmq.POLLIN)

        self.DEBUG_counter = 0
        self.DEBUG_duration_overall = 0
        self.DEBUG_timestamp_start = 0.0
        self.DEBUG_timestamp_end = 0.0
        self.DEBUG_duration_process = 0
        self.DEBUG_timestamp_start_process = 0.0
        self.DEBUG_timestamp_end_process = 0.0
        time.sleep(1)
        return

    def set_point(self, i):
        self.command_publisher.send(f"hub _teensy_commands_get_pos {self.name} {i}")
        self._send_log(f"get_pos({self.name},{i}) request sent")

    def set_pos(self, i, x, y, z):
        idx = i % 3 - 1
        self.points[idx] = [x, y, z]
        self._send_log(f"set_pos called with i->idx: {i}->{idx}, pos ({x}, {y}, {z})")
        if not np.any(np.isnan(self.points)):
            A = self.points[1] - self.points[0]
            B = self.points[1] - self.points[2]
            self.N = np.cross(A, B)
            self.N /= np.linalg.norm(self.N)
            if self.N[2] < 0 :
                self.N *= -1
            self.d0 = np.dot(self.N, self.points[0])
            self.isN = True
            self._send_log({
                "desc": "Surface Normal Parameters",
                "normal": str(self.N),
                "intercept": str(self.d0),
            })

    def _estimate_vz_by_interpolation(self):
        if not self.isN:
            return 0
        curr_point_offsetted = self.curr_point.copy()
        curr_point_offsetted[2] += self.offset_z
        d = np.dot(curr_point_offsetted, self.N) - self.d0
        sign = -np.sign(d)
        magnitude = (self.VZ_MAX * 2) * ( np.abs(d) / (1+np.abs(d)) )
        vz_estimated = int( sign * magnitude )
        return vz_estimated
    
    def _estimate_vz_by_z_autofocus(self):
        if self.z_worm_focus is None:
            print("NOT WORKING! Select a Z-Focus model before enabling z-focus.")
            vz_estimated = None
        else:
            # Estimate Z-AutoFocus and add offset
            z_focus_offsetted = self.z_worm_focus + self.z_worm_focus_offset  # This is where we want the focus to be locked. positive values -> darker worm, I think more visible pharynx
            vz_estimated = np.clip(
                z_focus_offsetted * self.VZ_MAX * 2,
                -2*self.VZ_MAX, 2*self.VZ_MAX
            )
            vz_estimated = int(vz_estimated)
            # If close to good focus, stop movement
            if np.abs(z_focus_offsetted) < 0.05:  # This is the sensitivity to stay around the focus value -> higher means less accurate focus and less frequent movements, lower means higher accuracy of focus but lost of small movements
                vz_estimated = 0
            self.verbose_z_focus_counter += 1
            if self.verbose_z_focus_counter%30 == 0:
                print(f"Z Focus: {self.z_worm_focus:>.3f} | Offsetted: {z_focus_offsetted:>.3f} | V_z: {vz_estimated:>6d}")
                self.verbose_z_focus_counter = 0
        return vz_estimated

    def get_curr_pos(self):
        self.command_publisher.send(f"hub _teensy_commands_get_curr_pos {self.name}")
        self._send_log(f"get_curr_pos() request sent")

    def set_curr_pos(self, x, y, z):
        self.curr_point[:] = [x, y, z]
        self._send_log(f"received position ({x},{y},{z})")

    def set_offset_z(self, offset_z):
        self.offset_z = offset_z
        self._send_log(f"offset-z changed to {self.offset_z}")
    
    def detect(self, img):
        # Detect xy-tracking and z-focus
        img_annotated = img.copy()
        # If tracking and no new coordinates set
        ## X-Y tracking rest
        if not self.is_xy_worm_set:  # Retract coordinates toward center
            if not is_nan(self.x_worm) and not is_nan(self.y_worm):
                self.x_worm = (1.0-self.TRACKING_RETRACTION_FACTOR_XY)*self.img_x_center + self.TRACKING_RETRACTION_FACTOR_XY*self.x_worm
                self.y_worm = (1.0-self.TRACKING_RETRACTION_FACTOR_XY)*self.img_y_center + self.TRACKING_RETRACTION_FACTOR_XY*self.y_worm
            elif self.tracking_mode is not None:
                self.x_worm = self.img_x_center
                self.y_worm = self.img_y_center
            else:
                self.x_worm = None
                self.y_worm = None
        else:  # Consume the set coordinates
            self.is_xy_worm_set = False
            self._log_worm_positions()
        ## Z Focusing
        if self.focus_mode is None:
            pass
        elif not self.is_z_worm_set:
            if not is_nan(self.z_worm_focus):
                self.z_worm_focus *= self.TRACKING_RETRACTION_FACTOR_Z
            else:
                self.z_worm_focus = None
        else:  # Consume the set focus
            self.is_z_worm_set = False
            self._log_worm_focus()
        ## Add Annotations
        ### XY tracking
        if self.tracking_mode is not None:
            # Add worm bounding box if set
            if self.tracking_mode == "xy_threshold" and not is_nan(self.bbox_worm_xmin) and not is_nan(self.bbox_worm_ymin):
                img_annotated = cv.rectangle(img_annotated, (self.bbox_worm_xmin, self.bbox_worm_ymin), (self.bbox_worm_xmax, self.bbox_worm_ymax), 255, 2)
            elif not is_nan(self.x_worm) and not is_nan(self.y_worm): # Add the worm coordinate annotations
                img_annotated = cv.circle(
                    img_annotated,
                    (int(self.x_worm), int(self.y_worm)),
                    radius=10, color=255, thickness=2
                )
            # Add a dot in the center of the image
            img_annotated = cv.circle(
                img_annotated, (255, 255),
                radius=3, color=0, thickness=2
            )
            img_annotated = cv.circle(
                img_annotated, (255, 255),
                radius=2, color=255, thickness=2
            )
        return img_annotated

    def set_z_worm_focus(self, z_worm_focus):
        if isinstance(z_worm_focus, str):  # argument is not an int or a float, e.g. ObjectSubscriber failed to convert it -> it should be 'None' string
            self.z_worm_focus = None
        else:
            self.z_worm_focus = z_worm_focus
            self.is_z_worm_set = True
        return
    def set_xy_worm(self, x_worm, y_worm):
        if isinstance(x_worm, str) or isinstance(y_worm, str):  # argument is not an int or a float, e.g. ObjectSubscriber failed to convert it -> it should be 'None' string
            self.x_worm, self.y_worm = None, None
        else:
            self.x_worm, self.y_worm = x_worm, y_worm
            self.is_xy_worm_set = True
        return
    def set_boundingbox_worm(self, xmin, xmax, ymin, ymax):
        if isinstance(xmin, str) or isinstance(xmax, str) or isinstance(ymin, str) or isinstance(ymax, str):
            self.bbox_worm_xmin, self.bbox_worm_xmax = None, None
            self.bbox_worm_ymin, self.bbox_worm_ymax = None, None
            # In XY thresholding method, finding worm means having it's bounding box
            if self.tracking_mode == "xy_threshold":
                self.found_trackedworm = False
        else:
            self.bbox_worm_xmin = xmin
            self.bbox_worm_xmax = xmax
            self.bbox_worm_ymin = ymin
            self.bbox_worm_ymax = ymax
            # In XY thresholding method, finding worm means having it's bounding box
            if self.tracking_mode == "xy_threshold":
                self.found_trackedworm = True
        return
    def set_tracking_mode(self, tracking_mode):
        """
        Sina: this will be changed in the future to let the `tracking_tools` be a separate device and does not require a relay like this.
        """
        self.tracking_mode = tracking_mode
        if self.tracking_mode.lower() == "none":
            self.x_worm, self.y_worm = None, None
            self.bbox_worm_xmin, self.bbox_worm_xmax = None, None
            self.bbox_worm_ymin, self.bbox_worm_ymax = None, None
            self.tracking_mode = None
            self.command_publisher.send("tracking_models_behavior set_tracking_mode {}".format( None ))
        # elif self.tracking_mode == "xy_threshold":
        #     # Send signal to tracking device to stop
        #     self.command_publisher.send("tracking_models_behavior set_tracking_mode {}".format( None ))
        #     self.found_trackedworm = False
        else:
            # Send signal to tracking device to start and set mode
            self.command_publisher.send("tracking_models_behavior set_tracking_mode {}".format( self.tracking_mode ))
            # Tracking is always ON
            self.found_trackedworm = True
        # Return
        return
    def set_focus_mode(self, focus_mode):
        """
        Sina: this will be changed in the future to let the `tracking_tools` be a separate device and does not require a relay like this.
        """
        self.focus_mode = focus_mode
        if self.focus_mode.lower() == "none":
            self.z_worm_focus = None
            self.focus_mode = None
        self.command_publisher.send("tracking_models_behavior set_focus_mode {}".format( self.focus_mode ))
        # Return
        return

    def send_img_to_tracking_models(self, img):
        if self.data_publisher_tracking_models is not None:
            # Don't send data over if not necessary
            # if (self.tracking_mode == "xy_threshold" or self.tracking_mode is None) and self.focus_mode is None:
            if self.tracking_mode is None and self.focus_mode is None:
                pass
            else:  # Send the image to device and wait for the call-back from there
                self.data_publisher_tracking_models.send(img)
        return

    def _process(self):
        ###################### DEBUG
        self.DEBUG_timestamp_start_process = time.time()
        if self.DEBUG_counter%100 == 0:
            self.DEBUG_timestamp_start = time.time()
            self.DEBUG_counter = 0
            self.DEBUG_duration_process = 0.0
        ######################

        msg_timestamp, msg = self.data_subscriber.get_last()
        if msg is not None:
            self.data = msg[:,::-1] if self.flip_image else msg
        else:
            return

        self.data_publisher_writer.send(self.data, msg_timestamp)

        if tuple(self.data.shape) != (512, 512):
            data = cv.resize(self.data, (512, 512), interpolation=cv.INTER_AREA)
        else:
            data = self.data

        # Send the data to writer/displayer and continue
        # if "gcamp" recording.
        # You can change it in case you wanna track using GCaMP signal.
        if self.name == "tracker_gcamp":
            self.data_publisher_displayer.send(data)
            return

        # Detecting the tracking point and z-focus
        self.send_img_to_tracking_models(data)
        img_annotated = self.detect(data)

        self.data_publisher_displayer.send(img_annotated)

        # Tracking in Z direction
        # Priority: Z-AutoFocus > Interpolation
        self.vz = None
        if self.focus_mode is not None and self.z_autofocus_tracking:
            self.vz = self._estimate_vz_by_z_autofocus()
        elif self.interpolation_tracking:
            self.vz = self._estimate_vz_by_interpolation()

        # Tracking XY
        if self.tracking:
            if self.tracking_mode is None:  # No tracking mode set
                self.vy, self.vx = None, None
            elif not self.found_trackedworm:  # Tracking but worm not found
                self.missing_worm_idx += 1
                if self.missing_worm_idx == self.MISSING_WORM_TOLERANCE:
                    self.vy, self.vx = 0, 0
                else:
                    self.vy, self.vx = None, None
            elif self.found_trackedworm:  # Tracking and worm found
                self.missing_worm_idx = 0
                self.vy, self.vx = self.pid_controller.get_velocity(self.y_worm, self.x_worm)
        else:  # Disabled tracking
            self.vx, self.vy, self.vz = None, None, None

        self._set_velocities(self.vx, self.vy, self.vz)
        ###################### DEBUG
        self.DEBUG_timestamp_end_process = time.time()
        self.DEBUG_duration_process += (self.DEBUG_timestamp_end_process - self.DEBUG_timestamp_start_process)
        if (self.DEBUG_counter+1)%100 == 0:
            self.DEBUG_timestamp_end = time.time()
            self.DEBUG_duration_overall = ( self.DEBUG_timestamp_end - self.DEBUG_timestamp_start )
            print(f"Duration for 100 frames overall/processed: {(self.DEBUG_duration_overall*10):>5.2f}ms / {(self.DEBUG_duration_process*10):>5.2f}ms")
        self.DEBUG_counter += 1
        ######################
        return

    def start(self):
        if not self.tracking:
            self._send_log("starting tracking")
            self.missing_worm_idx = 0
            self.tracking = True
            self.command_publisher.send("tracking_models_behavior start_tracking")
            self.pid_controller.reset()
        return

    def stop(self):
        if self.tracking:
            self._set_velocities(0, 0, 0)
            self._send_log("stopping tracking")
            self.missing_worm_idx = 0
            self.tracking = False
            self.command_publisher.send("tracking_models_behavior stop_tracking")
            self.pid_controller.reset()
        return

    def shutdown(self):
        self._send_log("shutdown command received")
        self.stop()
        self.running = False
        return

    def _send_log(self, msg_obj):
        msg = str(msg_obj)
        if isinstance(msg_obj, dict):
            msg = json.dumps(msg_obj, default=int)

        msg = "{} {} {}".format( time.time(), self.name, msg )
        self.command_publisher.send(f"logger {msg}")
        return

    def _log_worm_positions(self):
        x,y = (self.x_worm, self.y_worm) if self.found_trackedworm else (-1, -1)
        msg = f"<TRACKER-WORM-COORDS> x-y coords: ({x},{y})"
        self._send_log(msg)
        return

    def _log_worm_focus(self):
        if self.z_worm_focus is not None:
            z_focus = self.z_worm_focus
            z_focus_offsetted = self.z_worm_focus + self.z_worm_focus_offset
        else:
            z_focus, z_focus_offsetted = None, None
        msg = f"<TRACKER-WORM-FOCUS> z-focus, offsetted: ({z_focus}, {z_focus_offsetted})"
        self._send_log(msg)
        return

    def interpolate_z_tracking(self, yes_no):
        if isinstance(yes_no, bool):
            self.interpolation_tracking = yes_no
        elif isinstance(yes_no, int):
            self.interpolation_tracking = yes_no == 1
        else:
            self.interpolation_tracking = yes_no.lower() == 'true'
        if not self.interpolate_z_tracking:
            self.points = np.zeros((3, 3)) * np.nan
            self.N = np.zeros(3) * np.nan
            self.isN = False
        return
    
    def set_z_autofocus_tracking(self, yes_no):
        if isinstance(yes_no, bool):
            self.z_autofocus_tracking = yes_no
        elif isinstance(yes_no, int):
            self.z_autofocus_tracking = yes_no == 1
        else:
            self.z_autofocus_tracking = yes_no.lower() == 'true'
        return
    
    def set_z_autofocus_tracking_offset(self, offset):
        self.z_worm_focus_offset = float(offset)
        return

    def _run(self):

        while self.running:
            sockets = dict(self.poller.poll())

            if self.command_subscriber.socket in sockets:
                self.command_subscriber.handle()
            elif self.data_subscriber.socket in sockets:
                self._process()
        return

    def _set_velocities(self, vx, vy, vz):
    
        if vx is not None:
            self.command_publisher.send("hub _teensy_commands_movex {}".format(vx))
        if vy is not None:
            self.command_publisher.send("hub _teensy_commands_movey {}".format(vy))
        if vz is not None:
            self.command_publisher.send("hub _teensy_commands_movez {}".format(vz))
        self._send_log(f"set velocities ({vx},{vy},{vz})")
        self.get_curr_pos()
        return

def main():

    arguments = docopt(__doc__)
    device = TrackerDevice(
        commands_in=parse_host_and_port(arguments["--commands_in"]),
        data_in=parse_host_and_port(arguments["--data_in"]),
        commands_out=parse_host_and_port(arguments["--commands_out"]),
        data_out_writer=parse_host_and_port(arguments["--data_out_writer"]),
        data_out_displayer=parse_host_and_port(arguments["--data_out_displayer"]),
        data_out_tracking_model=parse_host_and_port(arguments["--data_out_tracking_model"]),
        fmt=arguments["--format"],
        interpolation_tracking=arguments["--interpolation_tracking"],
        z_autofocus_tracking=arguments["--z_autofocus_tracking"],
        name=arguments["--name"],
        gui_fp=arguments["--gui_fp"],
        flip_image=arguments["--flip_image"])

    device._run()

if __name__ == "__main__":
    main()
