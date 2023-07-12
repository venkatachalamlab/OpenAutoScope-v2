#! python
#
# Copyright 2021
# Author: Vivek Venkatachalam

from typing import Tuple, Union

import h5py
import numpy as np


class ArrayWriter():
    def __init__(self,
                 src,
                 filename: str,
                 shape: Tuple[int, ...],
                 dtype: np.dtype,
                 groupname: Union[None, str] = None,
                 compression="lzf",
                 compression_opts=None):
        """ src.recv must be a coroutine that returns numpy arrays of the
        specified shape and type."""

        self.src = src

        self.shape = shape
        self.dtype = dtype

        self.N_complete = 0

        self.filename = filename
        self.file = h5py.File(filename, "a")

        if groupname is None:
            groupname = "/"
            self.group = self.file["/"]
        else:
            if groupname[0] != "/":
                groupname = "/" + groupname
            self.group = self.file.create_group(groupname)

        self.data = self.group.create_dataset(
            "data", (0, *shape),
            chunks=(1, *shape),
            dtype=dtype,
            compression=compression,
            compression_opts=compression_opts,
            maxshape=(None, *shape))

    def close(self):
        self.file.close()

    def save_frame(self):
        x = self.src.get_last()
        self.append_data(x)

    def save_recent_frame(self):

        result = self.src.get_last()

        if result is None:
            return
        else:
            msg = result
            self.append_data(msg)

    def append_data(self, x):
        self.N_complete += 1
        self.data.resize((self.N_complete, *self.shape))
        self.data[self.N_complete - 1, ...] = x

    @classmethod
    def from_source(cls,
                    src,
                    filename: str,
                    groupname: Union[None, str] = None):
        """If the source has shape and dtype fields, this can be used to
        construct the writer more succinctly."""
        return cls(src, filename, src.shape, src.dtype, groupname)


class TimestampedArrayWriter(ArrayWriter):
    def __init__(self,
                 src,
                 filename: str,
                 shape: Tuple[int, ...],
                 dtype: np.dtype,
                 groupname: Union[None, str] = None,
                 compression="lzf",
                 compression_opts=None):
        """ src must yield numpy arrays with shape and dtype matching the shape
        and dtype provided."""

        ArrayWriter.__init__(self, src, filename, shape, dtype, groupname,
                             compression, compression_opts)

        self.times = self.group.create_dataset("times", (0, ),
                                               chunks=(1, ),
                                               dtype=np.dtype("float64"),
                                               maxshape=(None, ))

    def append_data(self, msg):

        (t, x) = msg

        self.N_complete += 1

        self.data.resize((self.N_complete, *self.shape))
        self.times.resize((self.N_complete, ))

        self.data[self.N_complete - 1, ...] = x
        self.times[self.N_complete - 1] = t