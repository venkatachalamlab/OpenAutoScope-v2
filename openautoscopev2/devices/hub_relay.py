# Copyright 2023
# Author: Mahdi Torkashvand, Sina Rasouli

"""
This handles commands involving multiple devices.

Usage:
    hub_relay.py                        [options]

Options:
    -h --help                           Show this help.
    --server=PORT                        Connection with the clinet.
                                            [default: 5002]
    --inbound=PORT                      Incoming from forwarder.
                                            [default: L5001]
    --outbound=PORT                     outgoing to forwarder.
                                            [default: L5000]
    --name=NAME                         device name.
                                            [default: hub]
    --framerate=NUMBER                  camera frame rate.
                                            [default: 1]
    --gui_fp=DIR                        GUI directory.
                                            [default: .]
    
"""
import os
import time
import json

from docopt import docopt

from openautoscopev2.zmq.hub import Hub
from openautoscopev2.zmq.utils import parse_host_and_port

class WormTrackerHub(Hub):
    def __init__(
            self,
            inbound,
            outbound,
            server,
            framerate,
            gui_fp,
            name="hub"):

        Hub.__init__(self, inbound, outbound, server, name)
        self.framerate=framerate
        with open(os.path.join(gui_fp, 'configs.json'), 'r', encoding='utf-8') as in_file:
            params = json.load( in_file )
        self.z_sign = 1 if int(params['z_dir']) == 1 else -1
        self.y_sign = 1 if int(params['y_dir']) == 1 else -1
        self.x_sign = 1 if int(params['x_dir']) == 1 else -1


    def shutdown(self):
        self._writer_shutdown()
        self._flir_camera_shutdown()
        self._tracker_shutdown()
        self._writer_shutdown()
        self._controller_processor_shutdown()
        self._commands_shutdown()
        time.sleep(0.5)
        self._teensy_commands_shutdown()
        self._logger_shutdown()
        self.running = False

    def set_directories(self, directory):
        self._writer_set_directory(directory)
        self._logger_set_directory(directory)

    def _teensy_commands_shutdown(self):
        self.send("teensy_commands shutdown")

    def _teensy_commands_start_z_move(self, sign):
        self.send("teensy_commands start_z_move {}".format(sign * self.z_sign))

    def _teensy_commands_change_vel_z(self, sign):
        self.send("teensy_commands change_vel_z {}".format(sign))

    def _teensy_commands_reset_leds(self):
        self.send("teensy_commands reset_leds")
        led_state = 0
        for led_name in ['o', 'g']:  # except Behavior/IR led toggles
            self.send("writer_behavior set_led_state {} {}".format( led_name, led_state ))
            self.send("writer_gcamp set_led_state {} {}".format( led_name, led_state ))

    def _teensy_commands_set_led(self, led_name, state):
        self.send("teensy_commands set_led {} {}".format(led_name, state))
        if led_name != 'b':  # except Behavior/IR led toggles
            self.send("writer_behavior set_led_state {} {}".format( led_name, state ))
            self.send("writer_gcamp set_led_state {} {}".format( led_name, state ))

    def _teensy_commands_get_curr_pos(self, name):
        self.send("teensy_commands get_curr_pos {}".format(name))

    def _teensy_commands_set_curr_pos(self, name, x, y, z):
        self.send("{} set_curr_pos {} {} {}".format(name, x, y, z))

    def _teensy_commands_get_pos(self, name, i):
        self.send("teensy_commands get_pos {} {}".format(name, i))

    def _teensy_commands_set_pos(self, name, i, x, y, z):
        self.send("{} set_pos {} {} {} {}".format(name, i, x, y, z))

    def _teensy_commands_enable(self):
        self.send("teensy_commands enable")

    def _teensy_commands_disable(self):
        self.send("teensy_commands disable")

    def _teensy_commands_movex(self, xvel):
        self.send("teensy_commands movex {}".format(xvel * self.x_sign))

    def _teensy_commands_movey(self, yvel):
        self.send("teensy_commands movey {}".format(yvel * self.y_sign))

    def _teensy_commands_movez(self, zvel):
        self.send("teensy_commands movez {}".format(zvel * self.z_sign))

    def _tennsy_commands_set_motor_limit(self, motor, direction):
        self.send("teensy_commands set_motor_limit {} {}".format(motor, direction))

    def _logger_shutdown(self):
        self.send("logger shutdown")

    def _logger_set_directory(self, directory):
        self.send(f"logger set_directory {directory}")

    def _writer_start(self):
        self.send("writer_behavior start")
        self.send("writer_gcamp start")

    def _writer_stop(self):
        self.send("writer_behavior stop")
        self.send("writer_gcamp stop")

    def _writer_shutdown(self):
        self.send("writer_behavior shutdown")
        self.send("writer_gcamp shutdown")

    def _writer_set_directory(self, directory):
        self.send("writer_gcamp set_directory {}".format(directory))
        self.send("writer_behavior set_directory {}".format(directory))

    def _tracker_set_point(self, i):
        self.send("tracker_behavior set_point {}".format(i))

    def _tracker_get_curr_pos(self):
        self.send("tracker_behavior get_curr_pos")

    def _tracker_set_offset_z(self, offset_z):
        self.send("tracker_behavior set_offset_z {}".format(offset_z))

    def _tracker_set_tracking_mode(self, tracking_mode):
        self.send("tracker_behavior set_tracking_mode {}".format(tracking_mode))

    def _tracker_start(self):
        self.send("tracker_behavior start")

    def _tracker_stop(self):
        self.send("tracker_behavior stop")

    def _tracker_shutdown(self):
        self.send("tracker_behavior shutdown")
        self.send("tracker_gcamp shutdown")

    def _tracker_interpolate_z_tracking(self, yes_no):
        self.send("tracker_behavior interpolate_z_tracking {}".format(yes_no))
    def _tracker_set_z_autofocus_tracking(self, yes_no):
        self.send("tracker_behavior set_z_autofocus_tracking {}".format(yes_no))

    def _flir_camera_set_region_behavior(self, z, y, x, b, offsety, offsetx):
        self.send("FlirCameraBehavior set_region {} {} {} {} {} {}".format(z, y, x, b, offsety, offsetx))

    def _flir_camera_set_region_gcamp(self, z, y, x, b, offsety, offsetx):
        self.send("FlirCameraGCaMP set_region {} {} {} {} {} {}".format(z, y, x, b, offsety, offsetx))

    def _flir_camera_set_exposure_framerate_behavior(self, exposure, rate):
        self.send("FlirCameraBehavior set_exposure_framerate {} {}".format(exposure * 1000, rate))

    def _flir_camera_set_exposure_framerate_gcamp(self, exposure, rate):
        self.send("FlirCameraGCaMP set_exposure_framerate {} {}".format(exposure * 1000, rate))

    def _flir_camera_start(self):
        self.send("FlirCameraBehavior start")
        self.send("FlirCameraGCaMP start")

    def _flir_camera_stop(self):
        self.send("FlirCameraBehavior stop")
        self.send("FlirCameraGCaMP stop")

    def _flir_camera_start_behavior(self):
        self.send("FlirCameraBehavior start")

    def _flir_camera_start_gcamp(self):
        self.send("FlirCameraGCaMP start")

    def _flir_camera_stop_behavior(self):
        self.send("FlirCameraBehavior stop")

    def _flir_camera_stop_gcamp(self):
        self.send("FlirCameraGCaMP stop")

    def _flir_camera_shutdown(self):
        self.send("FlirCameraBehavior shutdown")
        self.send("FlirCameraGCaMP shutdown")

    def _commands_shutdown(self):
        self.send("commands shutdown")

    def _controller_processor_shutdown(self):
        self.send("controller_processor shutdown")

def main():
    arguments = docopt(__doc__)

    scope = WormTrackerHub(
        inbound=parse_host_and_port(arguments["--inbound"]),
        outbound=parse_host_and_port(arguments["--outbound"]),
        server=int(arguments["--server"]),
        framerate=int(arguments["--framerate"]),
        gui_fp=arguments["--gui_fp"],
        name=arguments["--name"])

    scope.run()

if __name__ == "__main__":
    main()
