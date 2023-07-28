# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""
Logger to save published messages to a file.

Usage:
    logger.py             [options]


Options:
    -h --help              Show this help.
    --inbound=PORT         connecting for inbound messages.
                           [default: 5001]
    --directory=PATH       Location to store published messages.
                           [default: ]
"""

import time

import zmq
from docopt import docopt

from openautoscopev2.zmq.utils import get_last
from openautoscopev2.devices.utils import make_timestamped_filename

class Logger():

    def __init__(
            self,
            port: int,
            directory: str):

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.SUB)

        self.socket.connect("tcp://localhost:{}".format(port))
        self.socket.setsockopt(zmq.SUBSCRIBE, b"logger")

        self.filename = make_timestamped_filename(directory, "log", "txt")
        self.file = open(self.filename, 'w+')

        self.running = False

    def _run(self):

        _ = get_last(self.socket.recv_string)
        self.running = True

        while self.running:
            msg = self.socket.recv_string()[7:]
            msg_parts = msg.split(maxsplit=1)
            func = msg_parts[0]
            if func == "shutdown":
                self.running = False
            elif func == "set_directory":
                 self.set_directory(msg_parts[1])

            msg = self._prepend_timestamp(msg)
            print(msg, file=self.file, flush=True)

        self.file.close()

    def _prepend_timestamp(self, msg: str) -> str:
        return "{} {}".format(str(time.time()), msg)
    
    def set_directory(self, directory: str):
        self.file.close()
        self.filename = make_timestamped_filename(directory, "log", "txt")
        self.file = open(self.filename, 'w+')

def main():

    args = docopt(__doc__)
    inbound = int(args["--inbound"])
    directory = args["--directory"]

    logger = Logger(inbound, directory)
    logger._run()

if __name__ == "__main__":
    main()
