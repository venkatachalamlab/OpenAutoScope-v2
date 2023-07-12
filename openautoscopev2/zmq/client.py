#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Sina Rasouli

import zmq

from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.utils import parse_host_and_port

from openautoscopev2.zmq.utils import (
    coerce_string,
    coerce_bytes
)

class GUIClient():
    """This is a wrapped ZMQ client that can send requests to a server."""

    def __init__(
            self,
            port: int,
            port_forwarder_in: str
        ):

        self.port = port
        self.bounds_forwarder_in = parse_host_and_port(port_forwarder_in)
        self.running = False

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.REQ)

        address = "tcp://localhost:{}".format(self.port)
        self.socket.connect(address)

        self.control_socket = self.context.socket(zmq.PUB)
        self.control_socket.bind("tcp://*:4862")  # DEBUG TODO change this to an argument for the class

        self.publisher = Publisher(
            host=self.bounds_forwarder_in[0],
            port=self.bounds_forwarder_in[1],
            bound=self.bounds_forwarder_in[2]
        )

    def recv(self) -> bytes:
        """Receive a reply."""

        return self.socket.recv()

    def send(self, req: bytes):
        """Send a request."""

        self.socket.send(req)
    
    def log(self, msg):
        self.publisher.send("logger "+ str(msg))

    def process(self, req_str):
        self.send(coerce_bytes(req_str))
        self.log(f"<CLIENT WITH GUI> command sent: {req_str}")
        rep_str = coerce_string(self.recv())
        self.log(f"<CLIENT WITH GUI> response received: {rep_str}")
        if req_str == "DO shutdown":
            self.control_socket.send_string("TERMINATE")