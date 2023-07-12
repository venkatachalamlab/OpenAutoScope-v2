#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""This module contains utilities used in devices."""

import os
import datetime
from typing import Tuple

import numpy as np

def make_timestamped_filename(directory: str, stub: str, ext: str):
    """Create a file name containing date and time."""

    now = datetime.datetime.now()
    filename = "%04d_%02d_%02d_%02d_%02d_%02d_%s.%s" % (
        now.year, now.month, now.day, now.hour, now.minute, now.second,
        stub, ext)
    return os.path.join(directory, filename)


def array_props_from_string(fmt: str) -> Tuple[np.dtype, str, Tuple[int, ...]]:
    """Convert a string describing the datatype, layout, and shape of an array
    into a tuple containing that information."""

    (dtype, layout, *shape) = fmt.split("_")
    dtype = np.dtype(dtype.lower())
    shape = tuple(map(int, shape))

    return (dtype, layout, shape)


def apply_lut(x: np.ndarray, lo: float, hi: float, newtype=None) -> np.ndarray:
    """Clip x to the range [lo, hi], then rescale to fill the range of
    newtype."""

    if newtype is None:
        newtype = x.dtype

    y_float = (x-lo)/(hi-lo)
    y_clipped = np.clip(y_float, 0, 1)

    if np.issubdtype(newtype, np.integer):
        maxval = np.iinfo(newtype).max
    else:
        maxval = 1.0

    return (maxval*y_clipped).astype(newtype)

def mip_x(vol:np.ndarray) -> np.ndarray:
    return np.transpose(np.max(vol, axis=2),
        (1, 0, *(range(2, np.ndim(vol)-1))))

def mip_y(vol:np.ndarray) -> np.ndarray:
    return np.max(vol, axis=1)

def mip_z(vol:np.ndarray) -> np.ndarray:
    return np.max(vol, axis=0)

def mip_threeview(vol: np.ndarray) -> np.ndarray:
    """Combine 3 maximum intensity projections of a volume into a single
    2D array."""

    S = vol.shape
    output_shape = (S[1] + 4 * S[0],
                    S[2] + 4 * S[0])

    vol = np.repeat(vol, 4, axis=0)

    x = mip_x(vol)
    y = mip_y(vol)
    z = mip_z(vol)

    output = np.zeros(output_shape, dtype=vol.dtype)

    output[:S[1], :S[2]] = z
    output[:S[1], S[2]:] = x
    output[S[1]:, :S[2]] = y

    return output

def resolve_path(fp: str, fp_base_dir: str):
    # Absolute Path
    if os.path.isabs(fp):
        return fp
    return os.path.join( fp_base_dir, fp )
