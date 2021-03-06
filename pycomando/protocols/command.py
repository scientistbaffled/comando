#!/usr/bin/env python
"""
"""

import ctypes
import struct

from .base import Protocol


# type: (pack[function], unpack)
# pack/unpack: (bytes_consumed, function)
types = {
    bool: (
        lambda v: struct.pack('<?', v),
        lambda bs: (1, struct.unpack('<?', bs[0])[0])),
    chr: (
        lambda v: struct.pack('<c', v),
        lambda bs: (1, struct.unpack('<c', bs[0])[0])),
    int: (
        lambda v: struct.pack('<i', v),
        lambda bs: (4, struct.unpack('<i', bs[:4])[0])),
    float: (
        lambda v: struct.pack('<f', v),
        lambda bs: (4, struct.unpack('<f', bs[:4])[0])),
    str: (
        lambda v: chr(len(v)) + v,
        lambda bs: (ord(bs[0]) + 1, bs[1:1+ord(bs[0])])),
    ctypes.c_byte: (
        lambda v: struct.pack('<b', v.value),
        lambda bs: (1, ctypes.c_byte(struct.unpack('<b', bs[0])[0]))),
    ctypes.c_char: (
        lambda v: struct.pack('<c', v.value),
        lambda bs: (1, ctypes.c_char(struct.unpack('<c', bs[0])[0]))),
    ctypes.c_int16: (
        lambda v: struct.pack('<h', v.value),
        lambda bs: (2, ctypes.c_int16(struct.unpack('<h', bs[:2])[0]))),
    ctypes.c_uint16: (
        lambda v: struct.pack('<H', v.value),
        lambda bs: (2, ctypes.c_uint16(struct.unpack('<H', bs[:2])[0]))),
    ctypes.c_int32: (
        lambda v: struct.pack('<i', v.value),
        lambda bs: (4, ctypes.c_int32(struct.unpack('<i', bs[:4])[0]))),
    ctypes.c_uint32: (
        lambda v: struct.pack('<I', v.value),
        lambda bs: (4, ctypes.c_uint32(struct.unpack('<I', bs[:4])[0]))),
    ctypes.c_float: (
        lambda v: struct.pack('<f', v.value),
        lambda bs: (4, ctypes.c_float(struct.unpack('<f', bs[:4])[0]))),
}
types[ctypes.c_bool] = types[bool]


def test_type_conversion():
    c = ctypes
    tests = [
        (False, '\x00'),
        (True, '\x01'),  # bool
        (0, '\x00\x00\x00\x00'),
        (1, '\x01\x00\x00\x00'),
        (256, '\x00\x01\x00\x00'),
        (-1, '\xff\xff\xff\xff'),  # int
        (0.0, '\x00\x00\x00\x00'),
        (1.0, '\x00\x00\x80?'),
        (-1.0, '\x00\x00\x80\xbf'),  # float
        ('\x00', '\x01\x00'),
        ('\xff', '\x01\xff'),
        ('', '\x00'),
        ('abc', '\x03abc'),
        (';\x00\n\r,', '\x05;\x00\n\r,'),  # string
        (c.c_byte(0), '\x00'),
        (c.c_byte(127), '\x7f'),
        (c.c_byte(-128), '\x80'),  # c_byte
        (c.c_char('\x00'), '\x00'),
        (c.c_char('\xff'), '\xff'),  # c_char
        (c.c_int16(0), '\x00\x00'),
        (c.c_int16(1), '\x01\x00'),
        (c.c_int16(-1), '\xff\xff'),
        (c.c_int16(256), '\x00\x01'),  # c_int16
        (c.c_uint16(0), '\x00\x00'),
        (c.c_uint16(1), '\x01\x00'),
        (c.c_uint16(256), '\x00\x01'),
        (c.c_uint16(65535), '\xff\xff'),  # c_uint16
        (c.c_int32(0), '\x00\x00\x00\x00'),
        (c.c_int32(1), '\x01\x00\x00\x00'),
        (c.c_int32(-1), '\xff\xff\xff\xff'),
        (c.c_int32(256), '\x00\x01\x00\x00'),  # c_int32
        (c.c_uint32(0), '\x00\x00\x00\x00'),
        (c.c_uint32(1), '\x01\x00\x00\x00'),
        (c.c_uint32(256), '\x00\x01\x00\x00'),
        (c.c_uint32(4294967295), '\xff\xff\xff\xff'),  # c_uint32
        (c.c_float(0.0), '\x00\x00\x00\x00'),
        (c.c_float(1.0), '\x00\x00\x80?'),
        (c.c_float(-1.0), '\x00\x00\x80\xbf'),  # c_float
    ]
    for v, r in tests:
        pv = types[type(v)][0](v)
        assert pv == r, "[%s pack error] %r != %r" % (type(v), pv, r)
        uv = types[type(v)][1](r)[1]
        if hasattr(v, 'value'):
            e = uv.value == v.value
        else:
            e = uv == v
        assert e, "[%s, unpack error] %r != %r" % (type(v), uv, v)


class CommandProtocol(Protocol):
    def __init__(self, comm=None, index=0):
        Protocol.__init__(self, comm, index)
        self.received_arg_string = ""
        self.received_arg_string_index = 0
        self.send_arg_string = ""
        self.commands = {}
        self.callbacks = {}

    def register_callback(self, cid, func):
        self.callbacks[cid] = func

    def has_arg(self):
        return self.received_arg_string_index < len(self.received_arg_string)

    def get_arg(self, t):
        if not self.has_arg():
            raise Exception("Attempt to get_arg when no arg was available")
        if t not in types:
            raise Exception("Unknown argument type: %s" % t)
        s = self.received_arg_string[self.received_arg_string_index:]
        if len(s) == 0:
            raise Exception("Received argstring is empty")
        n, v = types[t][1](s)
        #print("received %r -> %s[%s]" % (s, v, n))
        self.received_arg_string_index += n
        return v

    def receive_message(self, bs):
        # byte 0 = command, ....
        if len(bs) < 1:
            raise Exception("Invalid empty command message")
        self.received_arg_string = bs[1:]
        self.received_arg_string_index = 0
        #print("Received arg string: %r" % self.received_arg_string)
        cid = ord(bs[0])
        if cid in self.callbacks:
            self.callbacks[cid](self)
        else:
            raise Exception(
                "Received message for unknown command[%s]" % (cid))

    def start_command(self, cid):
        if len(self.send_arg_string) != 0:
            raise Exception(
                "Cannot start new command [%s], command already started [%s]" %
                (cid, self.send_arg_string))
        self.send_arg_string += chr(cid)

    def add_arg(self, v, t=None):
        if t is None:
            t = type(v)
        if t not in types:
            raise Exception("Unknown argument type: %s" % t)
        self.send_arg_string += types[t][0](v)

    def finish_command(self):
        self.send_message(self.send_arg_string)
        self.send_arg_string = ""

    def send_command(self, cid, args=None):
        self.start_command(cid)
        if args is not None:
            [self.add_arg(a) for a in args]
        self.finish_command()


class EventManager(object):
    def __init__(self, command_protocol, commands):
        """
        commands = dict of:
            keys = command_id
            values = dicts with:
                'name': unique command name as a string
                'args': command argument types (used for trigger/send)
                'result': command result types (used for on/receive)
                'doc': command doc string
        """
        self._commands = commands
        self._commands_by_name = {}
        for cid in self._commands:
            command = self._commands[cid]
            if 'name' not in command:
                raise ValueError("Command must have name: %s" % (command, ))
            n = command['name']
            if 'name' in self._commands_by_name:
                raise ValueError("Command name %s is not unique" % (n, ))
            command['id'] = cid
            self._commands_by_name[n] = command
        self._cmd = command_protocol
        for cid in self._commands:
            self._cmd.register_callback(
                cid,
                lambda cmd, cid=cid: self._receive_event(cmd, cid))
        self._callbacks = {}
        self._wait_for = None

    def _receive_event(self, cmd, cid):
        if cid not in self._commands:
            raise ValueError("Received unknown command with index=%s" % cid)
        command = self._commands[cid]
        # unpack results
        if 'result' in command:
            result_spec = command['result']
            result = []
            for spec in result_spec:
                if not cmd.has_arg():
                    raise ValueError(
                        "Not enough [%s] arguments to unpack the result [%s]"
                        % (len(result), len(result_spec)))
                result.append(cmd.get_arg(spec))
        else:
            result = []
        return self._handle_event(command['name'], result)

    def _handle_event(self, name, result):
        if name in self._callbacks:
            [cb(*result) for cb in self._callbacks[name]]
        if name == self._wait_for:
            self._wait_for = result

    def on(self, name, func):
        """Register a callback (func) for a given command name"""
        if name not in self._callbacks:
            self._callbacks[name] = []
        self._callbacks[name].append(func)

    def trigger(self, name, *args):
        """Trigger a command by name with arguments (args)"""
        # find command by name
        if name not in self._commands_by_name:
            raise ValueError("Unknown command name: %s" % (name, ))
        command = self._commands_by_name[name]
        cid = command['id']
        if 'args' not in command:
            return self._cmd.send_command(cid)
        arg_spec = command['args']
        if len(args) != len(arg_spec):
            raise ValueError(
                "len(args)[%s] != len(arg spec)[%s] for command %s" %
                (len(args), len(arg_spec), name))
        pargs = [s(a) for (s, a) in zip(arg_spec, args)]
        self._cmd.send_command(cid, pargs)

    def blocking_trigger(self, name, *args):
        """Trigger a command and wait for a response with the same name"""
        if self._wait_for is not None:
            raise ValueError(
                "Unexpected _wait_for is not None %s" % (self._wait_for, ))
        self.trigger(name, *args)
        self._wait_for = name
        comm = self._cmd.comm()
        error = None
        while (self._wait_for is name) and (error is None):
            try:
                comm.handle_stream()
            except Exception as e:
                error = e
        del comm
        r = self._wait_for
        self._wait_for = None
        if error is not None:
            raise e
        return r
