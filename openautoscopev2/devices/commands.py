# Copyright 2023
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
    --name=NAME             Name ued by the hub to send commands.
                                [default: commands]
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
                 commands: Tuple[str, int],
                 name):

        self.subscriber = Subscriber(
            inbound[1],
            inbound[0],
            inbound[2]
        )

        self.publisher = Publisher(
            outbound[1],
            outbound[0],
            outbound[2]
        )
        self.subscriber_commands = ObjectSubscriber(
            self,
            commands[1],
            commands[0],
            commands[2],
            name = name
        )

        self.poller = zmq.Poller()
        self.poller.register(self.subscriber.socket)
        self.poller.register(self.subscriber_commands.socket)

        self.running = True

        buttons = [
            b"dpad_up pressed", b"dpad_up released",
            b"dpad_down pressed", b"dpad_down released",
            b"dpad_right pressed", b"dpad_left pressed",
            b"right_stick", b"left_stick",
            ]

        self.subscriber.remove_subscription("")
        for button in buttons:
            self.subscriber.add_subscription(button)
    
    def shutdown(self):
        self.running = False
        return

    def _handle_messages(self, message):
        tokens = message.split(" ")

        if message == "dpad_right pressed":
            self.publisher.send("hub _teensy_commands_change_vel_z 1")

        elif message == "dpad_left pressed":
            self.publisher.send("hub _teensy_commands_change_vel_z -1")

        elif message == "dpad_up pressed":
            self.publisher.send("hub _teensy_commands_start_z_move 1")

        elif message == "dpad_down pressed":
            self.publisher.send("hub _teensy_commands_start_z_move -1")

        elif message == "dpad_up released" or message == "dpad_down released":
            self.publisher.send("hub _teensy_commands_movez 0")

        elif tokens[0] == "left_stick":
            self.publisher.send("hub _teensy_commands_movex {}".format(int(tokens[1]) // 50))
            self.publisher.send("hub _teensy_commands_movey {}".format(int(tokens[2]) // 50))

        elif tokens[0] == "right_stick":
            self.publisher.send("hub _teensy_commands_movex {}".format(int(tokens[1])))
            self.publisher.send("hub _teensy_commands_movey {}".format(int(tokens[2])))

        return

    def _run(self):
        def _finish(*_):
            raise SystemExit

        signal.signal(signal.SIGINT, _finish)

        while self.running:
            sockets = dict(self.poller.poll())

            if self.subscriber.socket in sockets:
                message = self.subscriber.recv_last_string()
                self._handle_messages(message)

            if self.subscriber_commands.socket in sockets:
                self.subscriber_commands.handle()

def main():
    arguments = docopt(__doc__)

    inbound = parse_host_and_port(arguments["--inbound"])
    outbound = parse_host_and_port(arguments["--outbound"])
    commands = parse_host_and_port(arguments["--commands"])
    name = arguments["--name"]

    processor = XboxStageCommands(inbound, outbound, commands, name)

    processor._run()

if __name__ == "__main__":
    main()






