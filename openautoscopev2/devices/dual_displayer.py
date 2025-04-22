# Copyright 2023
# Author: Mahdi Torkashvand, Sina Rasouli

import PySimpleGUI as sg

import zmq
import numpy as np
import cv2 as cv

from openautoscopev2.zmq.utils import parse_host_and_port
from openautoscopev2.zmq.array import TimestampedSubscriber
from openautoscopev2.devices.utils import array_props_from_string

class DualDisplayer:
    # Add Annotations
    CVTEXT_FONT = cv.FONT_HERSHEY_SIMPLEX
    CVTEXT_COLOR = 255
    CVTEXT_THICKNESS = 1
    CVTEXT_SCALE = 0.5
    GFP_DEADPIXELS_IJ = [
        (0, 245),
        (156, 109),
        (156, 110),
        (157, 109),
        (157, 110),
        (232, 433),
        (245, 241),
        (305, 252),
        (320, 217),
        (406, 241),
    ]
    IMG_GFP_BADPIXELS_MASK = np.ones((512, 512), dtype=np.bool_)
    for i,j in GFP_DEADPIXELS_IJ:
        IMG_GFP_BADPIXELS_MASK[i,j] = False

    def __init__(
            self,
            window: sg.Window,
            data_r: str,
            data_g: str,
            fmt: str,
            q: float = 0.0,
            show_gfp_stats: bool = False
        ):

        self.window = window
        # (_, _, self.shape) = array_props_from_string(fmt)
        self.shape = (512, 512)  # TODO: the size of displayer is fixed so we always resize.
        self.dtype = np.uint8
        self.image_r = np.zeros(self.shape, dtype=self.dtype)
        self.image_g = np.zeros(self.shape, dtype=self.dtype)
        self.image = np.zeros((*self.shape, 3), dtype=self.dtype)
        self.image_g_annotated = np.zeros_like(self.image_g)
        self.show_gfp_stats = show_gfp_stats
        self.text_beh = None

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
    
    def set_beh_text(self, text):
        self.text_beh = text if text is not None else None
        return

    def get_frame(self):
        # Listen for changes
        anything_changed = False
        sockets = dict(self.poller.poll())
        if self.subscriber_r.socket in sockets:
            msg_r = self.subscriber_r.get_last()
            if msg_r is not None:
                anything_changed = True
                self.image_r = msg_r[1][::-1, ::-1]
                if tuple(self.image_r.shape) != (512, 512):
                    self.image_r = cv.resize(self.image_r, (512, 512))
        if self.subscriber_g.socket in sockets:
            msg_g = self.subscriber_g.get_last()
            if msg_g is not None:
                anything_changed = True
                self.image_g = msg_g[1][::-1, ::-1] * self.IMG_GFP_BADPIXELS_MASK
                self.image_g = np.clip( self.image_g.astype(np.float32)*4, 0, 255 ).astype(np.uint8)
                if tuple(self.image_g.shape) != (512, 512):
                    self.image_g = cv.resize(self.image_g.astype(np.float32), (512, 512), interpolation=cv.INTER_AREA)
        # Return if nothing changed
        if not anything_changed:
            return self.image, self.image_g_annotated
        # Reflect new changes in both displays
        self._q = np.quantile(self.image_g, self.q)
        self._max_g = np.max( self.image_g )
        self.image[...,:]  = (self.image_r / 2).astype(np.uint8)[...,None]
        self.image[...,1] += np.clip(
            (self.image_g.astype(np.float32) - self._q ) * self._max_g / 2 / max(1, (self._max_g - self._q)),
            0, 255
        ).astype(np.uint8)
        # Show BEH text
        if self.text_beh is not None:
            coords = (25, 25)
            self.image = cv.putText(
                self.image,
                self.text_beh, coords,
                self.CVTEXT_FONT, self.CVTEXT_SCALE, (0,0,255), self.CVTEXT_THICKNESS, cv.LINE_AA
            )
        # Show Beh stats
        if False:  # Set this to `True` for stats in behavior displayer to set/understand the lighting
            self.image[...,:]  = (self.image_r).astype(np.uint8)[...,None]
            self.image[...,0] = ( (self.image[...,1] > 200)*255 ).astype(np.uint8)
            _tmp = self.image[:,:,1]
            q10 = np.quantile(_tmp, 0.10)
            avg = np.mean(_tmp)
            q99 = np.quantile(_tmp, 0.99)
            _max = np.max( _tmp )
            text = f"(10%:{q10:>5.1f}, avg:{avg:>5.1f}, 99%:{q99:>5.1f}, max:{_max:>5.1f})"
            coords = (25, 25)
            self.image = cv.putText(
                self.image,
                text, coords,
                self.CVTEXT_FONT, self.CVTEXT_SCALE, self.CVTEXT_COLOR, self.CVTEXT_THICKNESS, cv.LINE_AA
            )

        # Show GFP stats
        self.image_g_annotated = self.image_g.copy()
        if self.show_gfp_stats:
            q10 = np.quantile(self.image_g, 0.10)
            avg = np.mean(self.image_g)
            q99 = np.quantile(self.image_g, 0.99)
            _max = np.max( self.image_g )
            text = f"(10%:{q10:>5.1f}, avg:{avg:>5.1f}, 99%:{q99:>5.1f}, max:{_max:>5.1f})"
            coords = (25, 25)
            self.image_g_annotated = cv.putText(
                self.image_g_annotated,
                text, coords,
                self.CVTEXT_FONT, self.CVTEXT_SCALE, self.CVTEXT_COLOR, self.CVTEXT_THICKNESS, cv.LINE_AA
            )
        return self.image, self.image_g_annotated
