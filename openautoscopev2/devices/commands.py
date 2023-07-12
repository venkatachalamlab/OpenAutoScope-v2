#! python
#
# Copyright 2021
# Author: Vivek Venkatachalam, Mahdi Torkashvand
#
# This is a convertor of messages from the PROCESSOR
# into stage commands for Zaber stages.
# Author: Vivek Venkatachalam, Mahdi Torkashvand

"""
This converts raw controller output to discrete events.

Usage:
    commands.py             [options]

Options:
    -h --help               Show this help.
    --inbound=HOST:PORT     Connection for inbound messages.
                                [default: L6001]
    --outbound=HOST:PORT    Connection for outbound messages.
                                [default: 6002]
    --commands=HOST:PORT    Connection for incoming commands.
                                [default: 5001]
"""


import signal
from typing import Tuple

import zmq
from docopt import docopt

from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import Subscriber, ObjectSubscriber
from openautoscopev2.zmq.utils import parse_host_and_port

class XboxStageCommands():

    def __init__(self,
                 inbound: Tuple[str, int],
                 outbound: Tuple[str, int],
                 commands: Tuple[str, int]):

        self.subscriber = Subscriber(inbound[1],
                                     inbound[0],
                                     inbound[2])

        self.publisher = Publisher(outbound[1],
                                   outbound[0],
                                   outbound[2])
        self.subscriber_commands = ObjectSubscriber(
            self,
            commands[1],
            commands[0],
            commands[2],
            name = "commands"  # TODO: change this hard coded name -> also in `oas.py`
        )


        self.poller = zmq.Poller()
        self.poller.register(self.subscriber.socket)
        self.poller.register(self.subscriber_commands.socket)


        self.running = True

        buttons = [
            b"X pressed", b"Y pressed", b"B pressed",
            b"A pressed",
            b"dpad_up pressed", b"dpad_up released",
            b"dpad_down pressed", b"dpad_down released",
            b"dpad_right pressed", b"dpad_left pressed",
            b"right_stick", b"left_stick",
            b"left_shoulder pressed", b"right_shoulder pressed",
            ]

        self.subscriber.remove_subscription("")
        for button in buttons:
            self.subscriber.add_subscription(button)
    
    def shutdown(self):
        self.running = False
        return

    def handle_messages(self, message):
        tokens = message.split(" ")

        if message == "dpad_left pressed":
            self.publish("teensy_commands change_vel_z -1")

        elif message == "dpad_right pressed":
            self.publish("teensy_commands change_vel_z 1")

        elif message == "dpad_up pressed":
            self.publish("teensy_commands start_z_move -1")

        elif message == "dpad_up released":
            self.publish("teensy_commands movez 0")

        elif message == "dpad_down pressed":
            self.publish("teensy_commands start_z_move 1")

        elif message == "dpad_down released":
            self.publish("teensy_commands movez 0")

        elif tokens[0] == "left_stick":
            xspeed = int(tokens[1]) // 50
            yspeed = int(tokens[2]) // 50
            self.publish("teensy_commands movey {}".format(yspeed))
            self.publish("teensy_commands movex {}".format(xspeed))

        elif tokens[0] == "right_stick":
            xspeed = int(tokens[1])
            yspeed = int(tokens[2])
            self.publish("teensy_commands movey {}".format(yspeed))
            self.publish("teensy_commands movex {}".format(xspeed))

        return

    def run(self):
        def _finish(*_):
            raise SystemExit

        signal.signal(signal.SIGINT, _finish)

        while self.running:

            sockets = dict(self.poller.poll())

            if self.subscriber.socket in sockets:
                message = self.subscriber.recv_last_string()
                self.handle_messages(message)

            if self.subscriber_commands.socket in sockets:
                self.subscriber_commands.handle()

    def publish(self, verb, *args):
        command = verb
        for arg in args:
            command += " " + str(arg)
        self.publisher.send(command)

def main():
    """CLI entry point."""
    arguments = docopt(__doc__)

    inbound = parse_host_and_port(arguments["--inbound"])
    outbound = parse_host_and_port(arguments["--outbound"])
    commands = parse_host_and_port(arguments["--commands"])

    processor = XboxStageCommands(inbound, outbound, commands)

    processor.run()

if __name__ == "__main__":
    main()






