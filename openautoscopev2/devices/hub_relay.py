#! python
#
# Copyright 2022
# Author: Mahdi Torkashvand, Vivek Venkatachalam

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
    --framerate=NUMBER                  camera frame rate
                                            [default: 1]
    
"""
import time

from docopt import docopt

from openautoscopev2.zmq.hub import Hub
from openautoscopev2.zmq.utils import parse_host_and_port

class WormTrackerHub(Hub):
    """This is a central hub that is responsible for subscribing and publishing
    messages to all components of Lambda. Clients controlling the microscope
    should communicate only with this."""
    def __init__(
            self,
            inbound,
            outbound,
            server,
            framerate,
            name="hub"):

        Hub.__init__(self, inbound, outbound, server, name)
        self.framerate=framerate

    def shutdown(self):
        self._displayer_shutdown()
        self._writer_shutdown()
        self._flir_camera_shutdown()
        self._data_hub_shutdown()
        self._tracker_shutdown()
        self._writer_shutdown()
        self._displayer_shutdown()
        self._controller_shutdown()
        self._commands_shutdown()
        time.sleep(0.5)
        self._teensy_commands_shutdown()
        self._logger_shutdown()
        self.running = False

    def _commands_shutdown(self):
        self.send("commands shutdown")

    def _controller_shutdown(self):
        self.send("controller shutdown")

    def _tracker_shutdown(self):
        # TODO: separate functions for cameras?
        self.send("tracker_behavior shutdown")
        self.send("tracker_gcamp shutdown")

    def set_point(self, i):
        self.send("tracker_behavior set_point {}".format(i))
        self.send("tracker_gcamp set_point {}".format(i))

    def _logger_shutdown(self):
        self.send("logger shutdown")

    def _tracker_interpolate_z_tracking(self, yes_no):
        self.send("tracker interpolate_z_tracking {}".format(yes_no))

    def _displayer_set_shape(self, y, x):
        # TODO: separate functions for cameras?
        self.send("displayer_behavior set_shape {} {}".format(y, x))
        self.send("displayer_gcamp set_shape {} {}".format(y, x))
        self.send("displayer_debug set_shape {} {}".format(y, x))

    def _displayer_shutdown(self):
        # TODO: separate functions for cameras?
        self.send("displayer_behavior shutdown")
        self.send("displayer_gcamp shutdown")
        self.send("displayer_debug shutdown")

    
    def _data_hub_set_shape(self, z, y, x):
        # TODO: separate functions for cameras?
        self.send("data_hub_behavior set_shape {} {}".format(y, x))
        self.send("data_hub_gcamp set_shape {} {}".format(y, x))

    def _data_hub_shutdown(self):
        # TODO: separate functions for cameras?
        self.send("data_hub_behavior shutdown")
        self.send("data_hub_gcamp shutdown")

    def _writer_set_saving_mode(self, saving_mode):
        # TODO: separate functions for cameras?
        self.send("writer_behavior set_saving_mode {}".format(saving_mode))
        self.send("writer_gcamp set_saving_mode {}".format(saving_mode))

    def _writer_set_shape(self, y, x):
        # TODO: separate functions for cameras?
        self.send("writer_behavior set_shape {} {}".format(y, x))
        self.send("writer_gcamp set_shape {} {}".format(y, x))

    def _writer_start(self):
        # TODO: separate functions for cameras?
        self.send("writer_behavior start")
        self.send("writer_gcamp start")

    def _writer_stop(self):
        # TODO: separate functions for cameras?
        self.send("writer_behavior stop")
        self.send("writer_gcamp stop")

    def _tracker_start(self):
        self.send("tracker_behavior start")

    def _tracker_stop(self):
        self.send("tracker_behavior stop")

    def _writer_toggle(self):
        self.send("writer_behavior toggle")
        self.send("writer_gcamp toggle")

    def _set_directories(self, directory):
        self.send(f"writer_behavior set_directory {directory}")
        self.send(f"writer_gcamp set_directory {directory}")
        self.send(f"logger set_directory {directory}")

    def _writer_shutdown(self):
        # TODO: separate functions for cameras?
        self.send("writer_behavior shutdown")
        self.send("writer_gcamp shutdown")

    def _flir_camera_start(self):
        # TODO: separate functions for cameras?
        self.send("FlirCameraBehavior start")
        self.send("FlirCameraGCaMP start")
    def _flir_camera_start_behavior(self):
        self.send("FlirCameraBehavior start")

    def _flir_camera_stop(self):
        # TODO: separate functions for cameras?
        self.send("FlirCameraBehavior stop")
        self.send("FlirCameraGCaMP stop")
    def _flir_camera_stop_behavior(self):
        self.send("FlirCameraBehavior stop")

    def _flir_camera_shutdown(self):
        # TODO: separate functions for cameras?
        self.send("FlirCameraBehavior shutdown")
        self.send("FlirCameraGCaMP shutdown")

    def _flir_camera_set_exposure_framerate(self, exposure, rate):
        # TODO: separate functions for cameras?
        self.send("FlirCameraBehavior set_exposure_framerate {} {}".format(exposure, rate))
        self.send("FlirCameraGCaMP set_exposure_framerate {} {}".format(exposure, rate))
        time.sleep(1)
        self._flir_camera_start()

    def _flir_camera_set_exposure_framerate_behavior(self, exposure, rate):
        # TODO: separate functions for cameras?
        self.send("FlirCameraBehavior set_exposure_framerate {} {}".format(exposure, rate))
        # time.sleep(1)
        # self._flir_camera_start_behavior()
    def _flir_camera_set_exposure_framerate_gcamp(self, exposure, rate):
        # TODO: separate functions for cameras?
        self.send("FlirCameraGCaMP set_exposure_framerate {} {}".format(exposure, rate))

    def _flir_camera_set_shape(self, z, y, x, b):
        self.send("FlirCameraBehavior set_region {} {} {} {}".format(z, y, x, b))
        self.send("FlirCameraGCaMP set_region {} {} {} {}".format(z, y, x, b))

    def _flir_camera_set_region_behavior(self, z, y, x, b, offsety, offsetx):
        self.send("FlirCameraBehavior set_region {} {} {} {} {} {}".format(z, y, x, b, offsety, offsetx))

    def _flir_camera_set_region_gcamp(self, z, y, x, b, offsety, offsetx):
        self.send("FlirCameraGCaMP set_region {} {} {} {} {} {}".format(z, y, x, b, offsety, offsetx))

    def _teensy_commands_shutdown(self):
        self.send("teensy_commands shutdown")

    def _teensy_commands_set_led(self, led_name, intensity):
        self.send("teensy_commands set_led {} {}".format(led_name, intensity))

    def _teensy_commands_set_toggle_led(self, state_str):
        self.send("teensy_commands toggle_led_set {}".format(state_str))

    def _teensy_commands_movex(self, xvel):
        self.send("teensy_commands movex {}".format(xvel))

    def _teensy_commands_movey(self, yvel):
        self.send("teensy_commands movey {}".format(yvel))

    def _teensy_commands_movez(self, zvel):
        self.send("teensy_commands movez {}".format(zvel))

    def _teensy_commands_disable(self):
        self.send("teensy_commands disable")

    def _tracker_set_tracking_system(self, tracking_specs, fp_model_onnx):
        self.send(f"tracker_behavior set_tracking_system {tracking_specs} {fp_model_onnx}")
    def _tracker_set_offset_z(self, offset_z):
        self.send(f"tracker_behavior set_offset_z {offset_z}")

    def duration(self, sec):
        self.send("writer_behavior set_duration {}".format(sec*self.framerate))
        self.send("writer_gcamp set_duration {}".format(sec*self.framerate))

    def change_threshold(self, direction):
        msg = "tracker_behavior change_threshold {}".format(direction)
        self.send(msg)
    def change(self, value):
        msg = "tracker_behavior change {}".format(value)
        self.send(msg)

def main():
    """This is the hub for lambda."""
    arguments = docopt(__doc__)

    scope = WormTrackerHub(
        inbound=parse_host_and_port(arguments["--inbound"]),
        outbound=parse_host_and_port(arguments["--outbound"]),
        server=int(arguments["--server"]),
        framerate=int(arguments["--framerate"]),
        name=arguments["--name"])

    scope.run()

if __name__ == "__main__":
    main()
