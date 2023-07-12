#! python
#
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
    """This is logger operating on a TCP socket."""

    def __init__(
            self,
            port: int,
            directory: str):

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.SUB)

        self.socket.connect("tcp://localhost:{}".format(port))
        self.socket.setsockopt(zmq.SUBSCRIBE, b"logger")

        # Open File
        self.filename = make_timestamped_filename(directory, "log", "txt")
        self.file = open(self.filename, 'w+')

        self.running = False

    def run(self):
        """Subscribes to a string message and writes that on a file."""

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

            msg = self.prepend_timestamp(msg)
            print(msg, file=self.file, flush=True)

        self.file.close()

    def prepend_timestamp(self, msg: str) -> str:
        """Adds date and time to the string argument."""
        return "{} {}".format(str(time.time()), msg)
    
    def set_directory(self, directory: str):
        # Close File
        self.file.close()
        # Create New File
        self.filename = make_timestamped_filename(directory, "log", "txt")
        self.file = open(self.filename, 'w+')
        # Return
        return

def main():
    """main function"""
    args = docopt(__doc__)
    inbound = int(args["--inbound"])
    directory = args["--directory"]

    logger = Logger(inbound, directory)
    logger.run()

if __name__ == "__main__":
    main()
