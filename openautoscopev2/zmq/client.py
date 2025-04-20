#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Sina Rasouli

import time

import zmq

from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.utils import parse_host_and_port

from openautoscopev2.zmq.utils import (
    coerce_string,
    coerce_bytes
)

class GUIClient:
    """This is a wrapped ZMQ client that can send requests to a server."""

    def __init__(
            self,
            port_server: int,
            port_sendto_forwarder: str,
            port_recvfrom_forwarder: str,
            port_forwarder_control: int,
            sg_window,  # PySimpleGUI Window object to send events for other elements to be processed.
            name: str = "guiclient"
        ):

        self.name = name
        self.sg_window = sg_window
        self.port_server = port_server

        self.context = zmq.Context.instance()

        # Commuinicate with the server -> controlling CLI commands
        address = "tcp://localhost:{}".format(self.port_server)
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(address)

        # Signaling the proxy -> can start, pause, stop the proxy
        self.control_socket = self.context.socket(zmq.PUB)
        self.control_socket.bind(f"tcp://*:{port_forwarder_control}")

        # Make publisher to send commands
        self.bounds_sendto_forwarder = parse_host_and_port(port_sendto_forwarder)
        self.publisher = Publisher(
            host=self.bounds_sendto_forwarder[0],
            port=self.bounds_sendto_forwarder[1],
            bound=self.bounds_sendto_forwarder[2]
        )

        # Subscribe to listen for commands
        self.bounds_recvfrom_forwarder = parse_host_and_port(port_recvfrom_forwarder)
        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=self.name,
            host=self.bounds_recvfrom_forwarder[0],
            port=self.bounds_recvfrom_forwarder[1],
            bound=self.bounds_recvfrom_forwarder[2]
        )

        # WIP
        # TODO: This should not be the final implementation
        # but this will be required in the future for communication with
        # other devices.
        # Future schema: Client command -> device -> Client response -> UI element get info -> send event to event-loop
        self.poller = zmq.Poller()
        self.poller.register(self.command_subscriber.socket, zmq.POLLIN)

    # Communicate with `Server/ObjectServer` -> inherited in `Hub/WormTrackerHub`
    # this processes direct commands. E.g. it can be connected with CLI inputs.
    # Note: not connected in this implementation.
    def recv(self) -> bytes:
        """Receive a reply."""
        return self.socket.recv()

    def send(self, req: bytes):
        """Send a request."""
        self.socket.send(req)

    # Alias for sending message to logger device
    def log(self, msg):
        self.publisher.send("logger " + str(msg))

    # Process command sent by others, e.g. called from UI elements to
    # communicate with all other devices listening on `forwarder_out`
    def process(self, req_str):
        self.send(coerce_bytes(req_str))
        self.log(f"<CLIENT WITH GUI> command sent: {req_str}")
        rep_str = coerce_string(self.recv())
        self.log(f"<CLIENT WITH GUI> response received: {rep_str}")
        if req_str == "DO shutdown":
            self.control_socket.send_string("TERMINATE")

    # Send event to the event loop
    def send_event(self, key, value=None):
        self.sg_window.write_event_value(key, value)
        return
    # Pre-defined commands
    def turn_on_blue_led(self):
        self.send_event("led_g-ON", None)
    def turn_off_blue_led(self):
        self.send_event("led_g-OFF", None)
    def turn_on_opto_led(self):
        self.send_event("led_o-ON", None)
    def turn_off_opto_led(self):
        self.send_event("led_o-OFF", None)

    # Poll for commands sent to this device
    # Listens for all commands that need reflection on GUI.
    # E.g. status updates, position related infos, ... .
    # Those commands will invoke other functionalities implemented inside client.
    # or it can be interfaced with other classes etc etc.
    # Scenario 1: receive command -> internal funciton callback -> invoke event
    # Scenario 2: receive command -> poll for UI elements listening -> call their internal handles.
    # (Like scenario 2 since it can be beautifully integrated with GUI event loop!
    # everything is an event in that loop! even these things from devices!)
    # TODO: override the .handle() method to add event in case of missing corresponding function to be called.
    def listen_for_commands(self):
        sockets = dict(self.poller.poll(timeout=1))
        if self.command_subscriber.socket in sockets:
            self.command_subscriber.handle()
        # Ping coordinates every 500ms
        self.ping_coordinates()

    # Handle methods
    ## Ping coordinates
    def ping_coordinates(self):
        self.time_ping_last = getattr(self, 'time_ping_last', time.time())
        if time.time() > (self.time_ping_last + 0.500):
            client_cli_cmd = f"DO _teensy_commands_ping {self.name}"
            self.process(client_cli_cmd)
            self.time_ping_last = time.time()
        return
    ## Get coordinates
    def set_stage_coordinates(self, x, y, z, vx, vy, vz):
        self.stage_r_xyz = [x, y, z]
        self.stage_v_xyz = [vx, vy, vz]
        self.send_event("CLIENT-STAGE-COORDS", self.stage_r_xyz+self.stage_v_xyz)
        self.log(f"<CLIENT WITH GUI> ping stage coordinates: {str(self.stage_r_xyz+self.stage_v_xyz)}")
        return
