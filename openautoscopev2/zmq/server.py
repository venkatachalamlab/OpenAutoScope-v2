#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""
ZMQ Server.

Usage:
    server.py             [options]

Options:
    -h --help             Show this help.
    --port=PORT           Socket port. [default: 5002]
"""

import zmq
from docopt import docopt

from openautoscopev2.zmq.utils import (
    coerce_string,
    coerce_bytes,
    try_num
)

class Server():
    """This is a wrapped ZMQ server operating on a TCP socket."""

    def __init__(
            self,
            port: int,
            name="Server"):

        self.name = name

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.REP)

        address = "tcp://*:{}".format(port)
        self.socket.bind(address)

        self.running = False

    def recv(self) -> bytes:
        """Receive a request."""

        return self.socket.recv()

    def send(self, rep: bytes):
        """Send a reply."""

        self.socket.send(rep)

    def handle(self):
        """Receive and process a message."""

        req = self.recv()
        self.process(req)

    def process(self, req: bytes):
        """Determine a response for a request, reply it."""

        req_str = coerce_string(req)
        if req_str == "DO shutdown":
            self.running = False
        self.send(coerce_bytes("Request completed."))

    def run(self):
        """Start looping."""

        self.running = True
        while self.running:
            self.handle()

class ObjectServer(Server):
    """This takes an object and creates a server that handles requests to
    query and mutate that object."""

    def __init__(self, port, obj):
        Server.__init__(self, port)
        self.obj = obj

    def process(self, req: bytes):

        req_str = coerce_string(req)
        req_parts = req_str.split(" ")

        if len(req_parts) <= 1:
            rep = "Command should at least have 2 parts."
            
        else:
            op = req_parts[0]
            attr = req_parts[1]
            args = req_parts[2:]
            args = tuple(map(try_num, args))

            try:
                if op == "GET":
                    rep = str(self.obj.__getattribute__(attr))

                elif op == "DO":
                    fn = self.obj.__getattribute__(attr)
                    fn(*args)
                    rep = "request completed."
                else:
                    rep = "Commands should start with 'DO' or 'GET'."

            except Exception as exc:
                rep = str(exc)

        self.send(coerce_bytes(rep))

def main():
    """CLI entry point."""

    args = docopt(__doc__)
    port = int(args["--port"])

    server = Server(port)
    server.run()

if __name__ == "__main__":
    main()
