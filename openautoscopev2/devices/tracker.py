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
    --format=UINT8_YX_512_512           Size and type of image being sent.
                                            [default: UINT8_YX_512_512]
    --name=NAME                         Device Name.
                                            [default: tracker]
    --interpolation_tracking=BOOL       Uses user-specified points to interpolate z.
                                            [default: False]
    --gui_fp=DIR                        GUI directory used to load model names.
                                            [default: .]
    --flip_image                        Flip x in recieved image before publishing.
"""

import time
import json
from typing import Tuple


import zmq
import numpy as np
from docopt import docopt
from openautoscopev2.devices.pid_controller import PIDController
from openautoscopev2.devices.tracker_tools import Detector

from openautoscopev2.zmq.array import TimestampedPublisher, Subscriber
from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.utils import parse_host_and_port
from openautoscopev2.devices.utils import array_props_from_string

class TrackerDevice():

    def __init__(
            self,
            commands_in: Tuple[str, int, bool],
            commands_out: Tuple[str, int],
            data_in: Tuple[str, int, bool],
            data_out_writer: Tuple[str, int],
            data_out_displayer: Tuple[str, int],
            fmt: str,
            interpolation_tracking:bool,
            name: str,
            gui_fp: str,
            flip_image: bool
        ):

        self.flip_image = flip_image

        self.missing_worm_idx = 0
        self.MISSING_WORM_TOLERANCE = 45
        self.VZ_MAX = 16

        self.interpolation_tracking = interpolation_tracking.lower() == 'true' if isinstance(interpolation_tracking, str) else interpolation_tracking
        self.points = np.zeros((3, 3)) * np.nan
        self.curr_point = np.zeros(3)
        self.N = np.zeros(3) * np.nan
        self.isN = False
        self.offset_z = 0
        

        np.seterr(divide = 'ignore')
        self.name = name
        (dtype, _, self.shape) = array_props_from_string(fmt)
        self.data = np.zeros(self.shape)

        self.detect = lambda img: img
        self.detector = Detector(tracker=self, gui_fp=gui_fp)
        self.y_worm = self.shape[0]//2
        self.x_worm = self.shape[1]//2
        self.pid_controller = PIDController(Kpy=10, Kpx=10, Kiy=0, Kix=0, Kdy=0, Kdx=0, SPy=self.shape[0]//2, SPx=self.shape[1]//2)

        self.trackedworm_size = None
        self.trackedworm_center = None
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

        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=name,
            host=commands_in[0],
            port=commands_in[1],
            bound=commands_in[2])

        self.data_subscriber = Subscriber(
            host=data_in[0],
            port=data_in[1],
            bound=data_in[2],
            shape=self.shape,
            datatype=dtype)
        
        self.poller = zmq.Poller()
        self.poller.register(self.command_subscriber.socket, zmq.POLLIN)
        self.poller.register(self.data_subscriber.socket, zmq.POLLIN)

        time.sleep(1)

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
        return int( sign * magnitude )

    def get_curr_pos(self):
        self.command_publisher.send(f"hub _teensy_commands_get_curr_pos {self.name}")
        self._send_log(f"get_curr_pos() request sent")

    def set_curr_pos(self, x, y, z):
        self.curr_point[:] = [x, y, z]
        self._send_log(f"received position ({x},{y},{z})")

    def set_offset_z(self, offset_z):
        self.offset_z = offset_z
        self._send_log(f"offset-z changed to {self.offset_z}")

    def set_tracking_mode(self, tracking_mode):
        self.detect = self.detector.__getattribute__(tracking_mode)

    def _process(self):
        msg = self.data_subscriber.get_last()
        if msg is not None:
            self.data = msg[:,::-1] if self.flip_image else msg
        else:
            return
        
        self.data_publisher_writer.send(self.data)
        if self.name == "tracker_gcamp":
            self.data_publisher_displayer.send(self.data)
            return

        img_annotated = self.detect(self.data)
        self.data_publisher_displayer.send(img_annotated)

        self._log_worm_positions()

        self.vz = self._estimate_vz_by_interpolation() if self.interpolation_tracking else 0

        if self.tracking and not self.found_trackedworm:
            self.missing_worm_idx += 1
            if self.missing_worm_idx == self.MISSING_WORM_TOLERANCE:
                self.vy, self.vx = 0, 0
            else:
                self.vy, self.vx = None, None
        elif self.tracking and self.found_trackedworm:
            self.missing_worm_idx = 0
            self.vy, self.vx = self.pid_controller.get_velocity(self.y_worm, self.x_worm)
        else:
            self.vx, self.vy, self.vz = None, None, None

        self._set_velocities(self.vx, self.vy, self.vz)

    def start(self):
        if not self.tracking:
            self._send_log("starting tracking")
            self.missing_worm_idx = 0
            self.trackedworm_center = None
            self.trackedworm_size = None
            self.tracking = True
            self.pid_controller.reset()

    def stop(self):
        if self.tracking:
            self._set_velocities(0, 0, 0)
            self._send_log("stopping tracking")
            self.missing_worm_idx = 0
            self.trackedworm_center = None
            self.trackedworm_size = None
            self.tracking = False
            self.pid_controller.reset()

    def shutdown(self):
        self._send_log("shutdown command received")
        self.stop()
        self.running = False

    def _send_log(self, msg_obj):
        msg = str(msg_obj)
        if isinstance(msg_obj, dict):
            msg = json.dumps(msg_obj, default=int)

        msg = "{} {} {}".format( time.time(), self.name, msg )
        self.command_publisher.send(f"logger {msg}")

    def _log_worm_positions(self):
        x,y = (self.x_worm, self.y_worm) if self.found_trackedworm else (-1, -1)
        msg = f"<TRACKER-WORM-COORDS> x-y coords: ({x},{y})"
        self._send_log(msg)

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

    def _run(self):

        while self.running:
            sockets = dict(self.poller.poll())

            if self.command_subscriber.socket in sockets:
                self.command_subscriber.handle()
            elif self.data_subscriber.socket in sockets:
                self._process()

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
        fmt=arguments["--format"],
        interpolation_tracking=arguments["--interpolation_tracking"],
        name=arguments["--name"],
        gui_fp=arguments["--gui_fp"],
        flip_image=arguments["--flip_image"])

    device._run()

if __name__ == "__main__":
    main()
