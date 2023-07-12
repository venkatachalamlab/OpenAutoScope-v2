#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""
ZMQ hub.

Usage:
    hub.py                [options]

Options:
    -h --help             Show this help.
    --inbound=HOST:PORT   Connection for inbound messages.
                          [default: localhost:5001]
    --outbound=HOST:PORT  Connection for outbound messages.
                          [default: localhost:5000]
    --serve=PORT          Binding to serve on. [default: 5002]
"""

from typing import Tuple

import zmq
from docopt import docopt

from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.server import ObjectServer
from openautoscopev2.zmq.utils import parse_host_and_port

class Hub():
    """This is a central hub that is responsible for subscribing and publishing
    messages to system components, and handling requests from external clients."""

    def __init__(
            self,
            inbound: Tuple[str, int, bool],
            outbound: Tuple[str, int, bool],
            server_port: int,
            name="hub"):

        self.name = name

        self.publisher = Publisher(
            host=outbound[0],
            port=outbound[1], 
            bound=outbound[2])

        self.subscriber = ObjectSubscriber(
            obj=self,
            host=inbound[0],
            port=inbound[1],
            bound=inbound[2],
            name=self.name)

        self.server = ObjectServer(
            obj=self,
            port=server_port)

        self.poller = zmq.Poller()

        self.running = False

    def send(self, msg):
        """Publish a message."""

        self.publisher.send(msg)

    def loop(self):
        """Handle messages received by server/subscriber."""

        self.poller.register(self.subscriber.socket)
        self.poller.register(self.server.socket)

        while self.running:

            sockets = dict(self.poller.poll())

            if self.subscriber.socket in sockets:
                self.subscriber.handle()

            if self.server.socket in sockets:
                self.server.handle()

    def run(self):
        """Start looping."""

        self.running = True
        self.loop()


def main():
    """This is a sample entry point, but you should generally not call it.
    Instead, subclass Hub in a separate file and write a similar main function
    there."""
    arguments = docopt(__doc__)

    inbound = parse_host_and_port(arguments["--inbound"])
    outbound = parse_host_and_port(arguments["--outbound"])
    server_port = int(arguments["--serve"])

    scope = Hub(inbound, outbound, server_port)
    scope.run()

if __name__ == "__main__":
    main()
