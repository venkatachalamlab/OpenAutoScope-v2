#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""
Publisher to send messages to a given port.

Usage:
    publisher.py          [options]

Options:
    -h --help             Show this help.
    --address=ADDRESS     Socket address. [default: 5004]
"""

from typing import Union

import zmq
from docopt import docopt

from openautoscopev2.zmq.utils import (
    address_from_host_and_port,
    parse_host_and_port,
    connect_or_bind
)

class Publisher():
    """This wraps a ZMQ PUB socket."""

    def __init__(
            self,
            port: int,
            host="localhost",
            bound=True):

        self.port = port
        self.host = host
        self.bound = bound

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.PUB)

        self.address = address_from_host_and_port(self.host, self.port, self.bound)

        self.connect()

        self.running = False

    def connect(self):
        """Connect or bind to the socket address."""

        connect_or_bind(self.socket, self.address, self.bound)

    def send(self, msg: Union[str, bytes]):
        """Send a single message."""

        if isinstance(msg, bytes):
            self.socket.send(msg)
        elif isinstance(msg, str):
            self.socket.send_string(msg)

    def loop(self):
        """Keep sending messages."""

        while self.running:
            try:
                self.send(input())
            except KeyboardInterrupt:
                self.running = False


    def run_blocking(self):
        """Run in the main thread, blocking to receive input."""

        self.running = True
        self.loop()

def main():
    """CLI entry point."""

    args = docopt(__doc__)

    (host, port, bound) = parse_host_and_port(args["--address"])

    publisher = Publisher(port=port, host=host, bound=bound)

    publisher.run_blocking()

if __name__ == "__main__":
    main()
