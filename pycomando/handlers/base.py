#!/usr/bin/env python
"""
Base handler class

This is responsible for reading/writing messages
"""


def checksum(bs):
    """Compute a checksum for an array of bytes"""
    return sum([ord(b) for b in bs]) % 256


def build_message(bs):
    """Build a message around an array of bytes"""
    n = len(bs)
    if n > 255:
        raise Exception("Messages cannot contain > 255 bytes [%s]" % n)
    return chr(n) + bs + chr(checksum(bs))


class StreamHandler(object):
    def __init__(self, stream):
        self.stream = stream

    def handle_stream(self):
        n = ord(self.stream.read(1))
        if n != '\x00':
            bs = self.stream.read(n)
        else:
            bs = ""
        if len(bs) != n:
            raise Exception(
                "Invalid message length of bytes %s != %s" %
                (len(bs), n))
        cs = self.stream.read(1)
        if cs != chr(checksum(bs)):
            raise Exception(
                "Invalid message checksum [%s != %s]" %
                (chr(checksum(bs)), cs))
        self.receive_message(bs)

    def send_message(self, bs):
        self.stream.write(build_message(bs))

    def receive_message(self, bs):
        raise NotImplementedError(
            "StreamHandler does not know how to handle messages, "
            "use a differnt (subclass) handler")


class ProtocolHandler(StreamHandler):
    def __init__(self, stream, protocols=None):
        StreamHandler.__init__(self, stream)
        self.protocols = {}
        if protocols is not None:
            [self.add_protocol(i, p) for (i, p) in enumerate(protocols)]

    def add_protocol(self, index, protocol):
        # TODO check protocol
        self.protocols[index] = protocol
        # TODO assign streamhandler (self) to protocol

    def receive_message(self, bs):
        if (len(bs) < 1):
            raise Exception("Invalid message, missing protocol")
        pid = bs[0]
        if pid not in self.protocols:
            raise Exception("Unknown protocol: %s" % pid)
        self.protocols[pid].receive_message(bs[1:])