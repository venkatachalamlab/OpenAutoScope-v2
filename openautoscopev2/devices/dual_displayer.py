# Copyright 2023
# Author: Mahdi Torkashvand, Sina Rasouli

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
            q: float = 0.0
        ):

        self.window = window
        (_, _, self.shape) = array_props_from_string(fmt)
        self.dtype = np.uint8
        self.image_r = np.zeros(self.shape, dtype=self.dtype)
        self.image_g = np.zeros(self.shape, dtype=self.dtype)
        self.image = np.zeros((*self.shape, 3), dtype=self.dtype)

        self.data_r = parse_host_and_port(data_r)
        self.data_g = parse_host_and_port(data_g)

        self.q = q
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

    def get_frame(self):
        sockets = dict(self.poller.poll())

        if self.subscriber_r.socket in sockets:
            msg_r = self.subscriber_r.get_last()
            if msg_r is not None:
                self.image_r = msg_r[1]
        if self.subscriber_g.socket in sockets:
            msg_g = self.subscriber_g.get_last()
            if msg_g is not None:
                self.image_g = msg_g[1]

        self._q = np.quantile(self.image_g, self.q)
        self._max_g = np.max( self.image_g )
        self.image[...,:]  = (self.image_r / 2).astype(np.uint8)[...,None]
        self.image[...,1] += np.clip((self.image_g.astype(np.float32) - self._q ) * self._max_g / 2 / max(1, (self._max_g - self._q)), 0, 255).astype(np.uint8)
        return self.image, self.image_g
