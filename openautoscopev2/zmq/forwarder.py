#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""
ZMQ forwarder.

Usage:
    forwarder.py          [options]

Options:
    -h --help             Show this help.
    --inbound=PORT        Binding for inbound messages.
                          [default: 5000]
    --outbound=PORT       Binding for outbound messages.
                          [default: 5001]
"""

import signal
import time
import threading

import zmq
from docopt import docopt

def run_proxy(inbound, outbound, context):

    inbound_socket = context.socket(zmq.XSUB)
    inbound_socket.bind("tcp://*:{}".format(inbound))

    outbound_socket = context.socket(zmq.XPUB)
    outbound_socket.bind("tcp://*:{}".format(outbound))

    control_socket = context.socket(zmq.SUB)
    control_socket.connect("tcp://localhost:4862")
    control_socket.setsockopt(zmq.SUBSCRIBE, b"")

    try:
        zmq.proxy_steerable(inbound_socket, outbound_socket, control=control_socket)
    except zmq.ContextTerminated:
        inbound_socket.close()
        outbound_socket.close()

def main():
    """CLI entry point."""

    args = docopt(__doc__)

    inbound = int(args["--inbound"])
    outbound = int(args["--outbound"])

    context = zmq.Context.instance()

    def _finish(*_):
        context.term()
        raise SystemExit

    signal.signal(signal.SIGINT, _finish)

    proxy_thread = threading.Thread(
        target=run_proxy,
        args=(inbound, outbound, context)
    )
    proxy_thread.start()
    proxy_thread.join()

if __name__ == "__main__":
    main()
