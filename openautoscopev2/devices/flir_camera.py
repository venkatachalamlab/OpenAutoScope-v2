#! python
#
# Copyright 2023
# Author: Mahdi Torkashvand

"""
Runs Flir cameras.

Usage:
    flir_camera.py                      [options]

Options:
    -h --help                           Show this help.
    --commands=HOST:PORT                Connection for commands.
                                            [default: localhost:5001]
    --data=HOST:PORT                    Connection for inbound array data.
                                            [default: *:6002]
    --status=HOST:PORT                  Socket Address to publish status.
                                            [default: localhost:5000]
    --name=NAME                         Device name.
                                            [default: flir_camera]
    --serial_number=NUMBER              Camera's serial number.
                                            [default: 22591117]
    --binsize=NUMBER                    Binning Size.
                                            [default: 1]
    --width=NUMBER                      Image width.
                                            [default: 512]
    --height=NUMBER                     Image height.
                                            [default: 512]
    --exposure_time=NUMBER              Exposure time in microsecond.
                                            [default: 10000.0]
    --frame_rate=NUMBER                 Frame rate.
                                            [default: 19]
"""

import json
import time
from typing import Tuple

import PySpin
import numpy as np
from docopt import docopt

from openautoscopev2.zmq.publisher import Publisher as Publisher
from openautoscopev2.zmq.subscriber import ObjectSubscriber
from openautoscopev2.zmq.array import Publisher as Array_Publisher
from openautoscopev2.zmq.utils import parse_host_and_port



class  FlirCamera():
    """This is FlirCamera class"""

    def __init__(
            self,
            commands_in: Tuple[str, int],
            data_out: Tuple[str, int],
            status_out: Tuple[str, int],
            serial_number: int,
            binsize: int,
            width: int,
            height: int,
            exposure_time: float,
            frame_rate: float,
            name="flircamera"):
        


        self.status = {}
        self.name = name


        self.device = 1
        self.dtype = np.uint8
        self.initiated = 0
        self.acquisition_status = False
        self.running = None
        self.depth, self.height, self.width, self.binsize = None, None, None, None
        self.exposure_time, self.frame_rate = None, None

        self.command_subscriber = ObjectSubscriber(
            obj=self,
            name=name,
            host=commands_in[0],
            port=commands_in[1],
            bound=commands_in[2])

        self.publisher = Publisher(
            host=status_out[0],
            port=status_out[1],
            bound=status_out[2])

        self.data_publisher = Array_Publisher(
            host=data_out[0],
            port=data_out[1],
            bound=data_out[2],
            datatype=self.dtype,
            shape=(1, height, width))

        self.cam, self.nodemap, self.tldevice_nodemap, self.processor, self.cam_list, self.system = self.spinnaker_camera(serial_number)
        if self.cam:
            self.initiated = 1
            self.depth, self.height, self.width, self.binsize = self.set_shape(1, height, width, binsize, None, None)
            self.exposure_time, self.frame_rate = self._set_exposure_time_and_frame_rate(exposure_time, frame_rate)
            self.running = 0
            self.first_time_in_loop = 1
            self.publish_status()

    def update_status(self):
        self.status["shape"] = [self.depth, self.height, self.width]
        self.status["exposure"] = self.exposure_time
        self.status["rate"] = self.frame_rate
        self.status["running"] = self.running
        self.status["device"] = self.device

    def publish_status(self):
        self.update_status()
        self.publisher.send("hub " + json.dumps({self.name: self.status}, default=int))
        self.publisher.send("logger "+ json.dumps({self.name: self.status}, default=int))

    def spinnaker_camera(self, serial_number):
        processor = PySpin.ImageProcessor()
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        num_cameras = cam_list.GetSize()

        if num_cameras == 0:
            cam_list.Clear()
            system.ReleaseInstance()

        for i, cam in enumerate(cam_list):
            cam.Init()
            tldevice_nodemap = cam.GetTLDeviceNodeMap()
            nodemap = cam.GetNodeMap()
            node_serial_number = PySpin.CStringPtr(tldevice_nodemap.GetNode('DeviceSerialNumber'))
            if serial_number == node_serial_number.GetValue():
                node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
                node_acquisition_mode.SetIntValue(node_acquisition_mode.GetEntryByName('Continuous').GetValue())
                node_acquisition_frame_rate_auto = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionFrameRateAuto'))
                node_acquisition_frame_rate_auto.SetIntValue(node_acquisition_frame_rate_auto.GetEntryByName('Off').GetValue())
                node_exposure_mode = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureMode'))
                node_exposure_mode.SetIntValue(node_exposure_mode.GetEntryByName('Timed').GetValue())
                node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
                node_exposure_auto.SetIntValue(node_exposure_auto.GetEntryByName('Off').GetValue())

                node_binning_horizontal = PySpin.CIntegerPtr(nodemap.GetNode('BinningHorizontal'))
                node_binning_vertical = PySpin.CIntegerPtr(nodemap.GetNode('BinningVertical'))
                min_bin = node_binning_horizontal.GetMin()
                if PySpin.IsWritable(node_binning_vertical):
                    node_binning_vertical.SetValue(min_bin)
                if PySpin.IsWritable(node_binning_horizontal):
                    node_binning_horizontal.SetValue(min_bin)

                node_offset_width = PySpin.CIntegerPtr(nodemap.GetNode('OffsetX'))
                node_offset_height = PySpin.CIntegerPtr(nodemap.GetNode('OffsetY'))
                if PySpin.IsWritable(node_offset_width):
                    node_offset_width.SetValue(0)
                if PySpin.IsWritable(node_offset_height):
                    node_offset_height.SetValue(0)

                node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
                node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
                max_width = node_width.GetMax()
                max_height = node_height.GetMax()
                if PySpin.IsWritable(node_width):
                    node_width.SetValue(max_width)
                if PySpin.IsWritable(node_height):
                    node_height.SetValue(max_height)

                node_acquisition_frame_rate = PySpin.CFloatPtr(nodemap.GetNode('AcquisitionFrameRate'))
                node_exposure_time = PySpin.CFloatPtr(nodemap.GetNode('ExposureTime'))
                max_fps = node_acquisition_frame_rate.GetMax()
                max_exp = node_exposure_time.GetMax()
                if PySpin.IsWritable(node_exposure_time):
                    node_exposure_time.SetValue(max_exp)
                if PySpin.IsWritable(node_acquisition_frame_rate):
                    node_acquisition_frame_rate.SetValue(max_fps)
                
                
                return cam, nodemap, tldevice_nodemap, processor, cam_list, system
            else:
                cam.DeInit()

            if i == (len(cam_list) - 1):
                print("Make sure the serial number is correct")

        for cam in enumerate(cam_list):
            del cam
        cam_list.Clear()
        system.ReleaseInstance()
        return False, False, False, False, False, False

    def _set_exposure_time_and_frame_rate(self, exposure_time, frame_rate):
        if self.acquisition_status:
            self.acquisition_status = self.cam.EndAcquisition()
        
        node_exposure_time = PySpin.CFloatPtr(self.nodemap.GetNode('ExposureTime'))
        node_acquisition_frame_rate = PySpin.CFloatPtr(self.nodemap.GetNode('AcquisitionFrameRate'))

        max_exp = node_exposure_time.GetMax()

        if exposure_time > max_exp:
             node_acquisition_frame_rate.SetValue(frame_rate)
             node_exposure_time.SetValue(exposure_time)
        else:
             node_exposure_time.SetValue(exposure_time)
             node_acquisition_frame_rate.SetValue(frame_rate)

        self.first_time_in_loop = 1
        self.publish_status()
        return node_exposure_time.GetValue(), node_acquisition_frame_rate.GetValue()


    def set_shape(self, depth, height, width, binsize, y_offset, x_offset):
        if self.acquisition_status:
            self.acquisition_status = self.cam.EndAcquisition()
        node_binning_horizontal = PySpin.CIntegerPtr(self.nodemap.GetNode('BinningHorizontal'))
        node_binning_vertical = PySpin.CIntegerPtr(self.nodemap.GetNode('BinningVertical'))
        node_width = PySpin.CIntegerPtr(self.nodemap.GetNode('Width'))
        node_height = PySpin.CIntegerPtr(self.nodemap.GetNode('Height'))
        node_offset_width = PySpin.CIntegerPtr(self.nodemap.GetNode('OffsetX'))
        node_offset_height = PySpin.CIntegerPtr(self.nodemap.GetNode('OffsetY'))

        max_height = node_offset_height.GetMax()
        y_offset_old, x_offset_old = node_offset_height.GetValue(), node_offset_width.GetValue()
        node_offset_width.SetValue(0)
        node_offset_height.SetValue(0)

        if max_height < height:
            if PySpin.IsWritable(node_binning_vertical):
                node_binning_vertical.SetValue(binsize)
            if PySpin.IsWritable(node_binning_horizontal):
                node_binning_horizontal.SetValue(binsize)
            
        node_height.SetValue(height)
        node_width.SetValue(width)

        if max_height >= height:
            if PySpin.IsWritable(node_binning_vertical):
                node_binning_vertical.SetValue(binsize)
            if PySpin.IsWritable(node_binning_horizontal):
                node_binning_horizontal.SetValue(binsize)

        # Offsets
        y_offset = (node_height.GetMax() - node_height.GetValue()) // 2 if y_offset is None else y_offset
        x_offset = (node_width.GetMax() - node_width.GetValue()) // 2 if x_offset is None else x_offset
        try:
            node_offset_height.SetValue(y_offset)
        except Exception as e:
            node_offset_height.SetValue(y_offset_old)
        try:
            node_offset_width.SetValue(x_offset)
        except Exception as e:
            node_offset_width.SetValue(x_offset_old)

        self.first_time_in_loop = 1
        self.publish_status()
        return depth, node_height.GetValue(), node_width.GetValue(), node_binning_vertical.GetValue()

    def shutdown(self):
        if self.running:
            if self.acquisition_status:
                self.acquisition_status = self.cam.EndAcquisition()
            self.running = 0
        self.device = 0
        self.publish_status()
        del self.cam
        self.cam_list.Clear()
        self.system.ReleaseInstance()

    def start(self):
        if not self.running:
             if not self.acquisition_status:
                self.acquisition_status = not self.cam.BeginAcquisition()
             self.processor = PySpin.ImageProcessor()
             self.running = 1
             self.publish_status()

    def stop(self):
        if self.running:
             if self.acquisition_status:
                self.acquisition_status = self.cam.EndAcquisition()
             self.running = 0
             self.publish_status()

    def set_exposure_framerate(self, exposure, framerate):
        _runner_flag = self.running
        if self.running:
             self.stop()
        self.exposure_time, self.frame_rate = self._set_exposure_time_and_frame_rate(exposure, framerate)
        if _runner_flag:
            self.start()

    def set_region(self, z, y, x, binsize, y_offset=None, x_offset=None):
        _runner_flag = self.running
        if self.running:
             self.stop()
        self.depth, self.height, self.width, self.binsize = self.set_shape(z, y, x, binsize, y_offset, x_offset)
        if _runner_flag:
            self.start()

    

    def run(self):

        while self.device:
            if self.first_time_in_loop:
                self.first_time_in_loop = 0
                if not self.acquisition_status:
                    self.acquisition_status = not self.cam.BeginAcquisition()
                self.processor = PySpin.ImageProcessor()
                self.running = 1
                self.publish_status()

            if self.running:
                msg = self.command_subscriber.recv_last()
            else:
                msg = self.command_subscriber.recv()

            if msg:
                self.command_subscriber.process(msg)

            elif self.running:
                #  Added try/except to avoid 'Failed waiting for EventData on NEW_BUFFER_DATA event' error
                #  Accroding to the support team: "This error occurs when trying to retrieve an image from the buffer(RAM) while the buffer is empty"
                #  Actaul solution: host controller cards, "https://www.flir.eu/products/usb-3.1-host-controller-card?vertical=machine+vision&segment=iis"
                try:
                    cam_buffer_image = self.cam.GetNextImage(1000)
                    if not cam_buffer_image.IsIncomplete():
                        data = self.processor.Convert(cam_buffer_image, PySpin.PixelFormat_Mono8)
                    cam_buffer_image.Release()
                    self.data_publisher.send(data.GetData())
                    del data
                except Exception as _:
                    pass



def main():
    """CLI entry point."""

    args = docopt(__doc__)

    flir_camera = FlirCamera(
        commands_in=parse_host_and_port(args["--commands"]),
        data_out=parse_host_and_port(args["--data"]),
        status_out=parse_host_and_port(args["--status"]),
        serial_number=args["--serial_number"],
        binsize=int(args["--binsize"]),
        width=int(args["--width"]),
        height=int(args["--height"]),
        exposure_time=float(args["--exposure_time"]),
        frame_rate=float(args["--frame_rate"]),
        name=args["--name"])

    if flir_camera.initiated:
        flir_camera.run()

if __name__ == "__main__":
    main()

