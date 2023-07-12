#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""This module contains utilities used in zmq modules."""

import time
import struct
from typing import Union, Tuple

import zmq

def coerce_string(x: Union[bytes, str]) -> str:
    """Convert bytes to a string."""
    if isinstance(x, bytes):
        x = x.decode("utf-8")
    return x

def coerce_bytes(x: Union[bytes, str]) -> bytes:
    """Convert a string to bytes."""
    if isinstance(x, str):
        x = bytes(x, "utf-8")
    return x

def try_num(s: str) -> Union[str, float, int]:
    """Attempt to convert a string to an integer. If that fails, try a float.
    If that fails, leave it as a string and return it."""

    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s

def address_from_host_and_port(
        host: str,
        port: int,
        bound: bool = False
    ) -> str:
    """Return a TCP address for a given host and port. If the address is meant
    to be bound, it will be bound to all available TCP interfaces (*)."""

    if bound:
        address = "tcp://*:{}".format(port)
    else:
        address = "tcp://{}:{}".format(host, port)

    return address

def connect_or_bind(socket, address: str, bound: bool):
    """Connect or bind the socket to address."""
    if bound:
        socket.bind(address)
    else:
        socket.connect(address)


def get_last(receiver):
    """This retrieves the most recent message sent to a socket by calling
    receiver. If no messages are available, this will return None."""

    msg = None

    while True:
        try:
            msg = receiver(flags=zmq.NOBLOCK)
        except zmq.error.Again:
            break
        except:
            raise

    return msg


def parse_host_and_port(val: str) -> Tuple[str, int, bool]:
    """This takes a command line argument specifying a host/port and returns
    a tuple of (host, port, bound) to determine a TCP endpoint:

    5000            -> ("*", 5000, True)
    localhost:5000  -> ("localhost", 5000, False)
    *:5000          -> ("*", 5000, True)
    L5000           -> ("localhost", 5000, False)
    """

    parts = val.split(":")

    if len(parts) == 1:

        s = parts[0]
        if s[0] == "L":
            port = int(s[1:])
            host = "localhost"
            bound = False
        else:
            port = int(s)
            host = "*"
            bound = True

    else:

        host = parts[0]
        port = int(parts[1])
        bound = host == "*"

    return (host, port, bound)

def push_timestamp(msg: bytes) -> bytes:
    """ This prepends a timestamp returned by python's time.time() as a double
    to the buffer specified by msg."""
    now = struct.pack('d', time.time())
    return msg + now

def pop_timestamp(msg: bytes) -> Tuple[float, bytes]:
    """ This pulls out a timestamp as returned by python's time.time() from the
    front of a message."""
    (timestamp, msg) = (msg[-8:], msg[:-8])
    timestamp = struct.unpack('d', timestamp)[0]
    return (timestamp, msg)
