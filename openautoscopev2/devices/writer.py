# Copyright 2023
# Author: Mahdi Torkashvand, Vivek Venkatachalam, Sina Rasouli

"""
Subscribes to a binary stream over TCP and saves the messages to a file.

Usage:
    writer.py                           [options]

Options:
    -h --help                           Show this help.
    --data_in=HOST:PORT                 Connection for inbound array data.
                                            [default: localhost:5004]
    --commands_in=HOST:PORT             Connection for commands.
                                            [default: localhost:5001]
    --status_out=HOST:PORT              Socket Address to publish status.
                                            [default: localhost:5000]
    --directory=PATH                    Directory to write data to.
                                            [default: ]
    --format=FORMAT                     Size and type of image being sent.
                                            [default: UINT8_YX_512_512]
    --video_name=NAME                   Directory to write data to.
                                            [default: data]
    --name=NAME                         Device name.
                                            [default: writer]
"""

import os
from os.path import join, exists
from typing import Tuple
import multiprocessing
from collections import defaultdict

import zmq
from docopt import docopt

from openautoscopev2.writers.array_writer import TimestampedArrayWriter
from openautoscopev2.zmq.array import TimestampedSubscriber
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.devices.utils import make_timestamped_filename
from openautoscopev2.zmq.utils import parse_host_and_port
from openautoscopev2.devices.utils import array_props_from_string

class  WriteSession(multiprocessing.Process):
    def __init__(
            self,
            data_in: Tuple[str, int],
            commands_in: Tuple[str, int],
            status_out: Tuple[str, int],
            fmt: str,
            directory: str,
            name="writer",
            video_name="data"):

        multiprocessing.Process.__init__(self)

        self.status = {}
        self.device_status = 1
        self.subscription_status = 0
        self.max_frames_per_file = 3*60*20
        self.STORE_EVERY_N_FRAMES = 10  # Long-term imagings
        # self.STORE_EVERY_N_FRAMES = 1
        self.led_states = defaultdict(bool)

        self.name = name
        self.video_name = video_name

        (self.dtype, _, self.shape) = array_props_from_string(fmt)
        self.file_idx = 0
        self.n_frames_this_file = 0
        self.fp_base = "TBS"

        self.directory = directory
        self.poller = zmq.Poller()

        self.status_publisher = Publisher(
            host=status_out[0],
            port=status_out[1],
            bound=status_out[2])

        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=name,
            host=commands_in[0],
            port=commands_in[1],
            bound=commands_in[2])

        self.data_subscriber = TimestampedSubscriber(
            host=data_in[0],
            port=data_in[1],
            shape=self.shape,
            datatype=self.dtype,
            bound=data_in[2])

        self.poller.register(self.command_subscriber.socket, zmq.POLLIN)
        self.poller.register(self.data_subscriber.socket, zmq.POLLIN)

    @property
    def filename(self) -> str:
        return join( self.fp_base, str(self.file_idx).zfill(6)+".h5" )
    @property
    def any_led_on(self) -> bool:
        if len(self.led_states) == 0:
            return False
        for led_name, is_on in self.led_states.items():
            if is_on:
                return True
        return False
    def set_led_state(self, led_name, led_state):
        if led_name == 'b':  # except Behavior/IR led toggles
            return
        assert type(led_state) in { int, bool }, "Unhandled `led_state` type! should be int or bool. <{}>: {}".format( type(led_state) , led_state )
        is_on = led_state > 0 if isinstance(led_state, int) else led_state
        self.led_states[led_name] = is_on
        return

    def start(self):
        if not self.subscription_status:
            _ = self.data_subscriber.get_last()
            self.file_idx = 0
            self.n_frames_this_file = 0
            self.fp_base = make_timestamped_filename(
                self.directory,
                self.video_name, "h5"
            )[:-3]
            if not exists(self.fp_base):
                os.mkdir( self.fp_base )
            self.writer = TimestampedArrayWriter.from_source(self.data_subscriber,
                                                             self.filename)
            self.subscription_status = 1

    def stop(self):
        if self.subscription_status:
            _ = self.data_subscriber.get_last()
            self.subscription_status = 0
            self.writer.close()

    def shutdown(self):
        self.stop()
        self.device_status = 0

    def _run(self):

        while self.device_status:

            sockets = dict(self.poller.poll())

            if self.command_subscriber.socket in sockets:
                self.command_subscriber.handle()

            elif self.data_subscriber.socket in sockets:
                msg = self.data_subscriber.get_last()
                if self.subscription_status and msg is not None:
                    if self.n_frames_this_file < self.max_frames_per_file:
                        if self.any_led_on or ( (self.n_frames_this_file%self.STORE_EVERY_N_FRAMES) == 0 ):
                            self.writer.append_data(msg)
                        self.n_frames_this_file += 1
                    else:
                        self.writer.close()
                        self.file_idx += 1
                        self.writer = TimestampedArrayWriter.from_source(
                            self.data_subscriber,
                            self.filename
                        )
                        self.writer.append_data(msg)
                        self.n_frames_this_file = 1

    def set_directory(self, directory):
        try:
            self.writer.close()
        except:
            pass
        self.directory = directory

def main():

    args = docopt(__doc__)

    writer = WriteSession(
        data_in=parse_host_and_port(args["--data_in"]),
        commands_in=parse_host_and_port(args["--commands_in"]),
        status_out=parse_host_and_port(args["--status_out"]),
        fmt=args["--format"],
        directory=args["--directory"],
        name=args["--name"],
        video_name=args["--video_name"])

    writer._run()

if __name__ == "__main__":
    main()
