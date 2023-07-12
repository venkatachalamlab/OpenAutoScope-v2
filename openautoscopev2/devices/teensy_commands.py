"""
This communicates with the teensy board.
Usage:
    teensy_commands.py          [options]

Options:
    -h --help                   Show this help.
    --inbound=HOST:PORT         Socket address to receive commands.
                                    [default: localhost:5001]
    --outbound=HOST:PORT        Socket address to publish status.
                                    [default: L5000]
    --port=<PORT>               USB port.
                                    [default: COM4]
"""

import json
import time
from typing import Tuple

import numpy as np
from serial import Serial
from docopt import docopt

from openautoscopev2.zmq.publisher import Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.utils import parse_host_and_port

class TeensyCommandsDevice():
    """This device sends serial commands to the teensy board."""


    _COMMANDS = {
        "get_pos": " \n",
        "sx":"sx{xvel}\n",
        "sy":"sy{yvel}\n",
        "sz":"sz{zvel}\n",
        "disable":"sf\n",
        "enable":"sn\n",
        "toggle_led_behavior":"lb{state}\n",
        "set_intesity_led": "l{led_name}s{intensity}\n", # b: behavior, o: optogenetics, g: gcamp
        }

    def __init__(
            self,
            inbound: Tuple[str, int, bool],
            outbound: Tuple[str, int, bool],
            port,
            name="teensy_commands",):

        self.status = {}
        self.port = port
        self.is_port_open = 0
        self.name = name
        self.device_status = 1
        self.zspeed = 1
        self.led_state = False
        self.led_intensities = {
            'b': 0,
            'o': 0,
            'g': 0,
        }
        self.led_names = ['b', 'o', 'g']
        self.led_idx_current = 0

        self.coords = [0]*6

        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=name,
            host=inbound[0],
            port=inbound[1],
            bound=inbound[2])

        self.status_publisher = Publisher(
            host=outbound[0],
            port=outbound[1],
            bound=outbound[2])

        try:
            self.serial_obj = Serial(port=self.port, baudrate=115200, timeout=0)
            self.is_port_open = self.serial_obj.is_open
        except Exception as e:
            self.log(e)
            return

        self.reset_leds()
        self.enable()

    def movex(self, xvel):
        self._execute("sx", xvel=xvel)

    def movey(self, yvel):
        self._execute("sy", yvel=yvel)

    def movez(self, zvel):
        self._execute("sz", zvel=zvel)

    def update_coordinates(self):
        self.status_publisher.send("logger "+ json.dumps({"position": [self.x, self.y, self.z]}, default=int))

    def log(self, msg):
        self.status_publisher.send("logger "+ str(msg))

    def disable(self):
        self._execute("disable")

    def enable(self):
        self._execute("enable")

    def get_pos(self, name, i):
        self._execute("get_pos")
        self.status_publisher.send(f"{name} set_pos {i} {self.x} {self.y} {self.z}")
    
    def get_curr_pos(self, name):
        self._execute("get_pos")
        self.status_publisher.send(f"{name} set_curr_pos {self.x} {self.y} {self.z}")
    
    @property
    def x(self):
        return self.coords[0]
    @property
    def y(self):
        return self.coords[1]
    @property
    def z(self):
        return self.coords[2]
    @property
    def vx(self):
        return self.coords[3]
    @property
    def vy(self):
        return self.coords[4]
    @property
    def vz(self):
        return self.coords[5]

    # LEDs
    ## Toggle
    def toggle_led(self):
        state_str = "n" if not self.led_state else "f"
        self._execute("toggle_led_behavior", state=state_str)
        self.led_state = not self.led_state
    def toggle_led_set(self, state_str):
        self._execute("toggle_led_behavior", state=state_str)
        self.led_state = not self.led_state
    ## Set
    def set_led(self, led_name, intensity):
        self._execute("set_intesity_led", led_name=led_name, intensity=intensity)
    ## Reset
    def reset_leds(self):
        self.led_state = True
        self.toggle_led()
        for led_name in ['b', 'o', 'g']:
            self.led_intensities[led_name] = 0
            self.set_led(led_name, 0)

    def change_vel_z(self, sign):
        self.zspeed = int(np.clip(self.zspeed * 2 ** sign, 1, 1024))
        print("zspeed is: {}   ".format(self.zspeed), end='\r')

    def start_z_move(self, sign):
        self.movez(sign * self.zspeed)

    def shutdown(self):
        self.movex(0)
        self.movey(0)
        self.movez(0)
        self.device_status = 0
        self.reset_leds()
        # Off Teensy
        self.disable()
        self.serial_obj.close()
        self.serial_obj.__del__()

    def _execute(self, cmd: str, **kwargs):
        cmd_format_string = self._COMMANDS[cmd]
        formatted_string = cmd_format_string.format(**kwargs)
        self.log(f"<TEENSY COMMANDS> executing: {formatted_string[:-1]}")  # Log except the trailing `\n`
        reply = b''
        self.serial_obj.write(bytes(formatted_string, "ascii"))
        while not reply:
            reply = self.serial_obj.readline()
        coords = reply.decode("utf-8")[:-1].split(" ")
        self.coords = [int(coord) for coord in coords]
        self.update_coordinates()

    def run(self):
        """Starts a loop and receives and processes a message."""
        self.command_subscriber.flush()
        while self.device_status:
            req = self.command_subscriber.recv()
            self.command_subscriber.process(req)




def main():
    """Create and start DragonflyDevice."""

    arguments = docopt(__doc__)

    device = TeensyCommandsDevice(
        inbound=parse_host_and_port(arguments["--inbound"]),
        outbound=parse_host_and_port(arguments["--outbound"]),
        port=arguments["--port"])

    if device is not None:
        device.run()

if __name__ == "__main__":
    main()