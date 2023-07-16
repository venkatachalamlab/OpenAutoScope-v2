#! python
#
# Copyright 2021
# Author: Mahdi Torkashvand, Vivek Venkatachalam

"""
Logger to save published messages to a file.

Usage:
    logger.py             [options]


Options:
    -h --help                               Show this help.
    --inbound=PORT                          connecting for inbound messages.
                                            [default: 5001]
    --directory=PATH                        Location to store published messages.
                                            [default: ]
    --slackbottoken=SLACK_BOT_TOKEN         Slack bot token used for sending messages, e.g. xoxb-XXXXX.
                                            [default: None]
    --slackchannel=SLACK_CHANNEL_NAME       Slack channel name to send message to, e.g. #channel-name.
                                            [default: None]
    --microscopename=MICROSCOPE_NAME        Microscope name added at the beginning of slack messages, e.g. OPENAUTOSCOPEV2-PC01.
                                            [default: OPENAUTOSCOPEV2-PC01]
"""

import time

import zmq
from docopt import docopt

from slack_sdk import WebClient

from openautoscopev2.zmq.utils import get_last
from openautoscopev2.devices.utils import make_timestamped_filename

class Logger():
    """This is logger operating on a TCP socket."""

    def __init__(
            self,
            port: int,
            directory: str,
            slackbottoken: str,
            slackchannel: str,
            microscopename: str
        ):

        self.microscopename = microscopename if microscopename.lower() != "none" else "OPENAUTOSCOPE-PC01"

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.SUB)

        self.socket.connect("tcp://localhost:{}".format(port))
        self.socket.setsockopt(zmq.SUBSCRIBE, b"logger")

        # Open File
        self.filename = make_timestamped_filename(directory, "log", "txt")
        self.file = open(self.filename, 'w+')

        # Slack
        self.slackbottoken = slackbottoken
        self.slackchannel = slackchannel
        if slackbottoken.lower() == 'none' or slackbottoken == "$$SLACK_BOT_TOKEN$$":
            self.slack_client = None
        else:
            self.slack_client = WebClient(token=self.slackbottoken)

        self.running = False

    def run(self):
        """Subscribes to a string message and writes that on a file."""

        _ = get_last(self.socket.recv_string)
        self.running = True

        while self.running:
            msg = self.socket.recv_string()[7:]
            msg_parts = msg.split(maxsplit=1)
            func = msg_parts[0]
            if func == "shutdown":
                self.running = False
            elif func == "set_directory":
                 self.set_directory(msg_parts[1])
            self.send_log(msg)
            self.handle_slack(msg)

        self.file.close()
    
    def send_log(self, msg):
        msg = self.prepend_timestamp(msg)
        print(msg, file=self.file, flush=True)
        return

    def prepend_timestamp(self, msg: str) -> str:
        """Adds date and time to the string argument."""
        return "{} {}".format(str(time.time()), msg)
    
    def set_directory(self, directory: str):
        # Close File
        self.file.close()
        # Create New File
        self.filename = make_timestamped_filename(directory, "log", "txt")
        self.file = open(self.filename, 'w+')
        # Return
        return
    
    def handle_slack(self, msg):
        # No Slack Communication
        if self.slack_client is None or '<SEND_TO_SLACK>' not in msg:
            return
        # Send Message to Slack
        msg = self.prepend_timestamp(
            msg.replace("<SEND_TO_SLACK>", "")
        )
        msg = f"Microscope@{self.microscopename}: {msg}"
        try:
            response = self.slack_client.chat_postMessage(
                channel=self.slackchannel,
                text = msg
            )
            assert response["message"]["text"] == msg, "Replied text from slack doesn't match sent message."
        except Exception as e:
            self.send_log(f"Microscope@{self.microscopename} | {str(e)}")

def main():
    """main function"""
    args = docopt(__doc__)
    inbound = int(args["--inbound"])
    directory = args["--directory"]
    slackbottoken = args["--slackbottoken"]
    slackchannel = args["--slackchannel"]
    microscopename = args["--microscopename"]

    logger = Logger(
        inbound, directory,
        slackbottoken, slackchannel,
        microscopename
    )
    logger.run()

if __name__ == "__main__":
    main()
