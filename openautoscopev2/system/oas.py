# Copyright 2023
# Author: Sina Rasouli, Mahdi Torkashvand

import os
from subprocess import Popen

from openautoscopev2.devices.utils import array_props_from_string

class OASwithGUI:

    def __init__(self, **kwargs) -> None:

        self.kwargs = dict()
        for key,value in kwargs.items():
            self.kwargs[key] = value
        self.jobs = []

        self.processor_out = 5003
        self.data_camera_out_behavior = 5004
        self.data_camera_out_gcamp = 5005
        self.tracker_to_writer_behavior = 5006
        self.tracker_to_writer_gcamp = 5007

    def kill(self):
        for job in self.jobs:
            try:
                job.kill()
            except PermissionError as _e:
                print("Error: ", _e)
        self.jobs = []

    def run(self):

        gui_fp = self.kwargs['gui_fp']
        data_directory = self.kwargs['data_directory']
        if not os.path.exists(data_directory):
            os.makedirs(data_directory)

        camera_serial_number_behavior = self.kwargs['camera_serial_number_behavior']
        camera_serial_number_gcamp = self.kwargs['camera_serial_number_gcamp']
        camera_gcamp_gain = self.kwargs['camera_gcamp_gain']
        teensy_usb_port = self.kwargs['teensy_usb_port']
        forwarder_in = self.kwargs['forwarder_in']
        forwarder_out = self.kwargs['forwarder_out']
        forwarder_control = self.kwargs['forwarder_control']
        server_client = self.kwargs['server_client']
        exposure_behavior = self.kwargs['exposure_behavior']
        exposure_gcamp = self.kwargs['exposure_gcamp']
        tracker_to_displayer_behavior = self.kwargs['tracker_to_displayer_behavior']
        tracker_to_displayer_gcamp = self.kwargs['tracker_to_displayer_gcamp']
        interpolation_tracking =  self.kwargs['interpolation_tracking']
        z_autofocus_tracking =  self.kwargs['z_autofocus_tracking']
        framerate = self.kwargs['framerate']
        format = self.kwargs['format']
        binsize = self.kwargs['binsize']
        (_, _, shape) = array_props_from_string(format)

        self.jobs.append(Popen(["oas_hub",
                        f"--inbound=L{forwarder_out}",
                        f"--outbound=L{forwarder_in}",
                        f"--server={server_client}",
                        f"--framerate={framerate}",
                        f"--gui_fp={gui_fp}",
                        f"--name=hub"]))

        self.jobs.append(Popen(["oas_forwarder",
                        f"--inbound={forwarder_in}",
                        f"--outbound={forwarder_out}",
                        f"--control={forwarder_control}"]))

        self.jobs.append(Popen(["oas_controller_processor",
                        f"--inbound=L{forwarder_out}",
                        f"--outbound={self.processor_out}",
                        f"--deadzone=5000",
                        f"--threshold=50",
                        f"--name=controller_processor"]))

        self.jobs.append(Popen(["oas_commands",
                        f"--inbound=L{self.processor_out}",
                        f"--outbound=L{forwarder_in}",
                        f"--commands=L{forwarder_out}",
                        f"--name=commands"]))

        self.jobs.append(Popen(["flir_camera",
                        f"--serial_number={camera_serial_number_behavior}",
                        f"--commands=L{forwarder_out}",
                        f"--status=L{forwarder_in}",
                        f"--data=*:{self.data_camera_out_behavior}",
                        f"--height={shape[0]}",
                        f"--width={shape[1]}",
                        f"--binsize={binsize}",
                        f"--exposure_time={exposure_behavior * 1000}",
                        f"--frame_rate={framerate}",
                        f"--name=FlirCameraBehavior"]))

        self.jobs.append(Popen(["flir_camera",
                        f"--serial_number={camera_serial_number_gcamp}",
                        f"--commands=L{forwarder_out}",
                        f"--status=L{forwarder_in}",
                        f"--data=*:{self.data_camera_out_gcamp}",
                        f"--height={shape[0]}",
                        f"--width={shape[1]}",
                        f"--binsize={binsize}",
                        f"--exposure_time={exposure_gcamp * 1000}",
                        f"--frame_rate={framerate}",
                        f"--gain={camera_gcamp_gain}",
                        f"--name=FlirCameraGCaMP"]))

        self.jobs.append(Popen(["oas_tracker",
                        f"--commands_in=L{forwarder_out}",
                        f"--commands_out=L{forwarder_in}",
                        f"--data_in=L{self.data_camera_out_behavior}",
                        f"--data_out_writer={self.tracker_to_writer_behavior}",
                        f"--data_out_displayer={tracker_to_displayer_behavior}",
                        f"--format={format}",
                        f"--interpolation_tracking={interpolation_tracking}",
                        f"--z_autofocus_tracking={z_autofocus_tracking}",
                        f"--name=tracker_behavior",
                        f"--gui_fp={gui_fp}"]))

        self.jobs.append(Popen(["oas_tracker",
                        f"--commands_in=L{forwarder_out}",
                        f"--commands_out=L{forwarder_in}",
                        f"--data_in=L{self.data_camera_out_gcamp}",
                        f"--data_out_writer={self.tracker_to_writer_gcamp}",
                        f"--data_out_displayer={tracker_to_displayer_gcamp}",
                        f"--format={format}",
                        f"--interpolation_tracking={interpolation_tracking}",
                        f"--z_autofocus_tracking={z_autofocus_tracking}",
                        f"--name=tracker_gcamp",
                        f"--gui_fp={gui_fp}",
                        "--flip_image"]))

        self.jobs.append(Popen(["oas_writer",
                        f"--data_in=L{self.tracker_to_writer_behavior}",
                        f"--commands_in=L{forwarder_out}",
                        f"--status_out=L{forwarder_in}",
                        f"--format={format}",
                        f"--directory={data_directory}",
                        f"--video_name=flircamera_behavior",
                        f"--name=writer_behavior"]))

        self.jobs.append(Popen(["oas_writer",
                        f"--data_in=L{self.tracker_to_writer_gcamp}",
                        f"--commands_in=L{forwarder_out}",
                        f"--status_out=L{forwarder_in}",
                        f"--format={format}",
                        f"--directory={data_directory}",
                        f"--video_name=flircamera_gcamp",
                        f"--name=writer_gcamp"]))

        self.jobs.append(Popen(["oas_logger",
                        f"--inbound={forwarder_out}",
                        f"--directory={data_directory}"]))

        self.jobs.append(Popen(["oas_teensy_commands",
                        f"--inbound=L{forwarder_out}",
                        f"--outbound=L{forwarder_in}",
                        f"--port={teensy_usb_port}",
                        f"--name=teensy_commands"]))