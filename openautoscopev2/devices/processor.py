#! python
#
# Copyright 2021
# Author: Vivek Venkatachalam, Mahdi Torkashvand
#
# This is a consumer of raw messages from an XINPUT device. Messages are
# obtained from a ZMQ PUB socket. They are then processed to determine whether
# a button was hit or released, or whether an analog trigger/joystick is
# outside its deadzone.
#
# The input message follows the structure of _XINPUT_GAMEPAD from MSDN:
#
#       typedef struct _XINPUT_GAMEPAD {
#         WORD  wButtons;
#         BYTE  bLeftTrigger;
#         BYTE  bRightTrigger;
#         SHORT sThumbLX;
#         SHORT sThumbLY;
#         SHORT sThumbRX;
#         SHORT sThumbRY;
#       } XINPUT_GAMEPAD, *PXINPUT_GAMEPAD;
#
# The output messages are ASCII encoded and of the form:
#
#       "A pressed"
#       "A released"
#       "dpad_right pressed"
#       "left_thumb released"
#       "left_stick -15344 0"
#       "left_trigger 255"
#
# Buttons (X, Y, A, B, start, back, left shoulder, and right shoulder) will
# emit events when pressed and when released.

"""
This XInput processor converts raw controller output to discrete events.

Usage:
    processor.py           [options]

Options:
    -h --help               Show this help.
    --name=NAME             Name of the XBox controller subscriber.
                                [default: controller]
    --inbound=HOST:PORT     Connection for inbound messages.
                                [default: *:5558]
    --outbound=HOST:PORT    Binding for outbound messages.
                                [default: *:6001]
    --deadzone=DEADZONE     Thumbstick deadzone.
                                [default: 5000]
    --threshold=THRESHOLD   Trigger activation threshold.
                                [default: 50]
"""

import struct
import signal
import time
from typing import List, Tuple
from collections import namedtuple

import XInput
from docopt import docopt

from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.utils import parse_host_and_port

GamepadState = namedtuple(
    "GamepadState",
    [
        "dpad_up",
        "dpad_down",
        "dpad_left",
        "dpad_right",
        "start",
        "back",
        "left_thumb",
        "right_thumb",
        "left_shoulder",
        "right_shoulder",
        "A",
        "B",
        "X",
        "Y",
        "left_trigger",
        "right_trigger",
        "left_stick",
        "right_stick"
    ])

GamepadButtonMask = {
    "dpad_up"       : 0x0001,
    "dpad_down"     : 0x0002,
    "dpad_left"     : 0x0004,
    "dpad_right"    : 0x0008,
    "start"         : 0x0010,
    "back"          : 0x0020,
    "left_thumb"    : 0x0040,
    "right_thumb"   : 0x0080,
    "left_shoulder" : 0x0100,
    "right_shoulder": 0x0200,
    "A"             : 0x1000,
    "B"             : 0x2000,
    "X"             : 0x4000,
    "Y"             : 0x8000
}

class XInputProcessor():

    def __init__(self,
                 name: str,
                 inbound: Tuple[str, int],
                 outbound: Tuple[str, int],
                 thumbstick_deadzone: int,
                 trigger_threshold: int
        ):
        self.name = name
        self.thumbstick_deadzone = thumbstick_deadzone
        self.trigger_threshold = trigger_threshold

        self.current_state = GamepadState(
            *([False]*14), 0, 0, (0, 0), (0, 0))

        self.subscriber = ObjectSubscriber(
            obj=self,
            host=inbound[0],
            port=inbound[1],
            bound=inbound[2],
            name=self.name
        )

        self.publisher = Publisher(outbound[1],
                                   outbound[0],
                                   outbound[2])
        self.running = True
        self.packet_number = 0
    
    def shutdown(self):
        """This terminates the processor."""
        self.update_and_send_state(0,0,0,0,0,0,0)
        self.running = False
        return

    def run(self):
        """This runs the processor."""

        def _finish(*_):
            raise SystemExit
        signal.signal(signal.SIGINT, _finish)

        while self.running:
            # Receive Command
            msg = self.subscriber.recv_last()
            if msg is not None:
                self.subscriber.process(msg)
            # Get XInput States
            state = XInput.get_state(0)
            if state.dwPacketNumber != self.packet_number:
                self.packet_number = state.dwPacketNumber
                self.update_and_send_state(
                    state.Gamepad.wButtons,
                    state.Gamepad.bLeftTrigger, state.Gamepad.bRightTrigger,
                    state.Gamepad.sThumbLX, state.Gamepad.sThumbLY,
                    state.Gamepad.sThumbRX, state.Gamepad.sThumbRY
                )
            time.sleep(0.01)
                
    
    # Update State
    def update_and_send_state(self,
            wButtons,
            bLeftTrigger, bRightTrigger,
            sThumbLX, sThumbLY,
            sThumbRX, sThumbRY
            ):
        # Generate GamePadState from Trigger Buttons
        gamepadstate_raw = self.gamepad_state_from_states(
            wButtons,
            bLeftTrigger, bRightTrigger,
            sThumbLX, sThumbLY, sThumbRX, sThumbRY
        )
        # Convert States to Interpretable Values
        new_state = self.sanitize_state(gamepadstate_raw)
        # Send Commands
        messages = self.get_events_from_states(self.current_state, new_state)
        for msg in messages:
            self.publisher.send(msg)
        # Update Internal State
        self.current_state = new_state
        return

    @staticmethod
    def gamepad_state_from_states(
            wButtons,
            bLeftTrigger, bRightTrigger,
            sThumbLX, sThumbLY,
            sThumbRX, sThumbRY
        ) -> GamepadState:
        """This converts states into a valid GamepadState."""

        # Handle the buttons.
        state_dict = {}
        for b, mask in GamepadButtonMask.items():
            state_dict[b] = bool(wButtons & mask)

        # Handle the triggers.
        state_dict["left_trigger"] = bLeftTrigger
        state_dict["right_trigger"] = bRightTrigger

        # Handle the sticks.
        state_dict["left_stick"] = (sThumbLX, sThumbLY)
        state_dict["right_stick"] = (sThumbRX, sThumbRY)

        return GamepadState(**state_dict)

    @staticmethod
    def gamepad_state_from_bytes(msg: bytes) -> GamepadState:
        """This converts a sequence of bytes into a valid GamepadState."""

        vals = struct.unpack(b'HBBhhhh', msg)

        # Handle the buttons.
        state_dict = {}
        for b, mask in GamepadButtonMask.items():
            state_dict[b] = bool(vals[0] & mask)

        # Handle the triggers.
        state_dict["left_trigger"] = vals[1]
        state_dict["right_trigger"] = vals[2]

        # Handle the sticks.
        state_dict["left_stick"] = (vals[3], vals[4])
        state_dict["right_stick"] = (vals[5], vals[6])

        return GamepadState(**state_dict)



    def sanitize_state(self, s: GamepadState) -> GamepadState:
        """This takes a gamepad state and determines whether the analog signals
        are above the required thresholds. A new sanitized state is
        returned."""

        thresh = self.trigger_threshold
        clean_trigger = lambda x: x if x >= thresh else 0

        left_trigger = clean_trigger(s.left_trigger)
        right_trigger = clean_trigger(s.right_trigger)

        dzone = self.thumbstick_deadzone
        clean_stick_xy = lambda x: x if abs(x) >= dzone else 0
        clean_stick = lambda x: tuple(map(clean_stick_xy, x))

        left_stick = clean_stick(s.left_stick)
        right_stick = clean_stick(s.right_stick)

        return GamepadState(*s[0:14], left_trigger, right_trigger, left_stick,
           right_stick)

    @staticmethod
    def get_events_from_states(s0: GamepadState, s1: GamepadState)->List[str]:
        """This calculates the difference between two controller states and
        generates a list of events  describing the difference."""

        messages =[]

        # Handle the buttons.
        for b in GamepadButtonMask:
            v1 = getattr(s1, b)
            v0 = getattr(s0, b)
            if v1 > v0:
                messages.append("{} pressed".format(b))
            elif v1 < v0:
                messages.append("{} released".format(b))

        # Handle the triggers.
        if s1.left_trigger != s0.left_trigger:
            messages.append("left_trigger {}".format(s1.left_trigger))
        if s1.right_trigger != s0.right_trigger:
            messages.append("right_trigger {}".format(s1.right_trigger))

        # Handle the thumbsticks.
        if s1.left_stick != s0.left_stick:
            messages.append(
                "left_stick {} {}".format(*s1.left_stick))

        if s1.right_stick != s0.right_stick:
            messages.append(
                "right_stick {} {}".format(*s1.right_stick))

        return messages

def main():
    """CLI entry point."""

    arguments = docopt(__doc__)

    name = arguments["--name"]
    inbound = parse_host_and_port(arguments["--inbound"])
    outbound = parse_host_and_port(arguments["--outbound"])
    deadzone = int(arguments["--deadzone"])
    threshold = int(arguments["--threshold"])

    processor = XInputProcessor(name, inbound, outbound, deadzone, threshold)
    processor.run()

if __name__ == "__main__":
    main()
