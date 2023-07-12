#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""
Subscriber to monitor messages on a given port.

Usage:
    subscriber.py         [options]

Options:
    -h --help             Show this help.
    --address=ADDRESS     Socket address. [default: L5004]
"""

from typing import Union, Optional
import json

import zmq
from docopt import docopt

from openautoscopev2.zmq.utils import (
    address_from_host_and_port,
    parse_host_and_port,
    connect_or_bind,
    coerce_string,
    coerce_bytes,
    get_last,
    try_num
)

class Subscriber():
    """This wraps a ZMQ SUB socket."""

    def __init__(
            self,
            port: int,
            host="localhost",
            bound=False):

        self.port = port
        self.host = host
        self.bound = bound

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.SUB)

        self.address = address_from_host_and_port(self.host,
                                                  self.port,
                                                  self.bound)

        self.connect()
        self.add_subscription("")

        self.running = False

    def connect(self):
        """Connect or bind to the socket address."""

        connect_or_bind(self.socket, self.address, self.bound)

    def add_subscription(self, x: Union[bytes, str]):
        """Add a subscription."""

        x = coerce_bytes(x)
        self.socket.setsockopt(zmq.SUBSCRIBE, x)

    def remove_subscription(self, x: Union[bytes, str]):
        """Remove a subscription."""

        x = coerce_bytes(x)
        self.socket.setsockopt(zmq.UNSUBSCRIBE, x)

    def recv(self) -> bytes:
        """Receive a message."""

        return self.socket.recv()

    def recv_string(self) -> str:
        """Receive a message."""

        return self.socket.recv_string()

    def recv_last(self) -> Optional[bytes]:
        """Receive the last message sent, or None if none are present."""

        return get_last(self.socket.recv)

    def recv_last_string(self) -> Optional[str]:
        """Receive the last message sent, or None if none are present."""

        return get_last(self.socket.recv_string)

    def flush(self):
        """Receive and dump all available messages."""

        _ = self.recv_last()

    def process(self, msg: bytes):
        """Decode and print a message."""

        msg = coerce_string(msg)

    def handle(self):
        """Receive and process a message."""

        req = self.recv()
        self.process(req)

    def loop(self):
        """Keep handling messages."""

        self.flush()
        while self.running:
            self.handle()

    def run_blocking(self):
        """Run in the main thread, blocking to receive input."""

        self.running = True
        self.loop()

class ObjectSubscriber(Subscriber):
    """This takes an object and starts a subscriber that receives messages
    to mutate that object."""

    def __init__(
            self,
            obj,
            port: int,
            host: str = "localhost",
            bound=False,
            name: Optional[str] = None):

        Subscriber.__init__(self, port, host, bound)

        self.obj = obj
        self.name = name

        if name is None:
            self.add_subscription("")
        else:
            self.remove_subscription("")
            self.add_subscription(name)

    def process(self, msg: bytes):
        """ Process messages of the following forms:

        b"obj_name make_coffee 5.0 espresso": Call make_coffee with
            arguments 5.0 (float) and "espresso" (str).

        b"obj_name {"prop1": 5, "prop2": "on"}": Update properties prop1
            and prop2 (JSON-decoded). Custom setters will be called.
        """
        try:
            if self.name is not None:
                msg = b" ".join(msg.split(b" ")[1:])

            msg_str = coerce_string(msg)

            if msg_str[0] == "{":

                msg_dict = json.loads(msg_str)

                for key, val in msg_dict.items():
                    self.obj.__setattr__(key, val)

            else:

                msg_parts = msg_str.split(" ")

                fn_str = msg_parts[0]
                args = []

                if len(msg_parts) > 1:
                    args_str = msg_parts[1:]
                    args = map(try_num, args_str)

                fn = self.obj.__getattribute__(fn_str)
                fn(*args)

        except Exception as exc:
            print("ZMQ/SUBSCRIBER.PY EXCEPTION!", str(exc))

def main():
    """CLI entry point."""

    args = docopt(__doc__)

    (host, port, bound) = parse_host_and_port(args["--address"])

    subscriber = Subscriber(port=port, host=host, bound=bound)

    subscriber.run_blocking()

if __name__ == "__main__":
    main()
