# -*- coding: utf-8 -*-
"""
Created on Fri Jul 17 14:45:55 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import random
import socket
import string

from .constants import ResponseCodes
from .exc import TransmissionError, MapiError
from .requests import ConnectRequest

class MapiClient:
    class Connection:
        def __init__(self, host, port):
            self.socket = socket.create_connection((host, port))

        def close(self):
            self.socket.close()

        def send(self, data: bytes):
            self.socket.send(data)
            response = self.socket.recv(5)
            if len(response) == 0:
                raise TransmissionError("Connection closed unexpectedly", read=len(data), expected=1)
            if len(response) < 5:
                return response
            length = int.from_bytes(response[1:], "little")
            buffer = bytes()
            while len(buffer) < length:
                data = self.socket.recv(length-len(buffer))
                if len(data) == 0:
                    raise TransmissionError("Connection closed unexpectedly", read=len(buffer), expected=length)
                buffer += data
            return response+buffer

    SID_LEN = 42  # Length of the session ID string

    def __init__(self, host="127.0.0.1", port=5000, prefix: str = None, private: bool = None):
        self.serverHost = host
        self.serverPort = port
        self.connection = None
        self.prefix = prefix
        self.private = private

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def connect(self, prefix: str = None, private: bool = None):
        prefix = prefix or self.prefix
        private = private if private is not None else self.private
        if prefix is None or private is None:
            raise TypeError("`prefix` or `private` not specified")
        self.connection = self.Connection(self.serverHost, self.serverPort)
        self.sessionId = "".join(random.choices(string.ascii_letters+string.digits, k=self.SID_LEN))
        self.send(ConnectRequest(prefix, self.sessionId, private))

    def disconnect(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def send(self, request):
        response = self.connection.send(request.serialize())
        code = response[0]
        if len(response) < 5:
            if code == ResponseCodes.SUCCESS:
                return None
            raise MapiError("Request failed: {} ({})".format(code, ResponseCodes.lookup(code, "Unknown")))
        return request.Response(response[5:])
