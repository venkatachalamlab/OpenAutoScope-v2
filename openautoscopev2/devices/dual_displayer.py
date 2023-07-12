#! python
#
# Copyright 2023
# Author: Mahdi Torkashvand

import PySimpleGUI as sg

import zmq
import numpy as np

from openautoscopev2.zmq.utils import parse_host_and_port
from openautoscopev2.zmq.array import TimestampedSubscriber
from openautoscopev2.devices.utils import array_props_from_string

class DualDisplayer:
    def __init__(
            self,
            window: sg.Window,
            data_r: str,
            data_g: str,
            fmt: str,
            name: str,
            q: float = 0.0
        ):

        self.window = window
        (_, _, self.shape) = array_props_from_string(fmt)
        self.dtype = np.uint8
        self.reset_buffers()

        self.name = name
        self.data_r = parse_host_and_port(data_r)
        self.data_g = parse_host_and_port(data_g)
        self.channel = [1, 1]

        self.q = q if q is not None else 0.0
        self._q = 0
        self._max_g = 0

        self.poller = zmq.Poller()

        self.subscriber_r = TimestampedSubscriber(
            host=self.data_r[0],
            port=self.data_r[1],
            shape=self.shape,
            datatype=self.dtype,
            bound=self.data_r[2])

        self.subscriber_g = TimestampedSubscriber(
            host=self.data_g[0],
            port=self.data_g[1],
            shape=self.shape,
            datatype=self.dtype,
            bound=self.data_g[2])

        self.poller.register(self.subscriber_r.socket, zmq.POLLIN)
        self.poller.register(self.subscriber_g.socket, zmq.POLLIN)

    def reset_buffers(self):
        self.image_r = np.zeros(self.shape, dtype=self.dtype)
        self.image_g = np.zeros(self.shape, dtype=self.dtype)
        self.image = np.zeros((*self.shape, 3), dtype=self.dtype)

    def set_shape(self, y, x):
        self.poller.unregister(self.subscriber_r.socket)
        self.poller.unregister(self.subscriber_g.socket)

        self.shape = (y, x)

        self.subscriber_r.set_shape(self.shape)
        self.subscriber_g.set_shape(self.shape)

        self.image = np.zeros(self.shape, self.dtype)

        self.poller.register(self.subscriber_r.socket, zmq.POLLIN)
        self.poller.register(self.subscriber_g.socket, zmq.POLLIN)


    def get_frame(self, combine=False):
        """
        Gets the last data from each camera, converts them into arrays, 
        returns individual arrays as well as a combination of them 
        if requested.
     
        params:
            combine: specifies the last returned value
                True: combined arrays
                False: none
        
        return:
            image_r: 2D array of data collected from behavior camera
            image_g: 2D array of data collected from the gcamp camera
            frame: A combination of image_r and image_g decided with param 'channel'
        """

        sockets = dict(self.poller.poll())
        if self.subscriber_r.socket in sockets:
            msg_r = self.subscriber_r.get_last()
            if msg_r is not None:
                self.image_r = msg_r[1]
        if self.subscriber_g.socket in sockets:
            msg_g = self.subscriber_g.get_last()
            if msg_g is not None:
                self.image_g = msg_g[1]
        
        if combine:
            self._q = np.quantile(self.image_g, self.q)
            self._max_g = np.max( self.image_g )
            self.image[...,:]  = (self.image_r / 2).astype(np.uint8)[...,None]
            self.image[...,1] += np.clip((self.image_g.astype(np.float32) - self._q ) * self._max_g / 2 / max(1, (self._max_g - self._q)), 0, 255).astype(np.uint8)
            return self.image_r, self.image_g, self.image
        return self.image_r, self.image_g, None
