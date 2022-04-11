from common import *

import sounddevice as sd
import numpy as np
import asyncio

import logging

import socket

class Client:
    def __init__(self, server_ip, server_port):

        self.server_address = (server_ip, server_port)
        self.sock = socket.socket(type=socket.SOCK_DGRAM)

        self.connected_users = {}
        self.buffer = np.empty((150_000, 2), dtype="float32")

    def handshake(self):
        handshake = packet.Packet()
        self.sock.sendto(handshake.serialize(), self.server_address)

        handshake = packet.unserialize(sock.recv(65536))

        self.SAMPLE_RATE = handshake.body["sample_rate"]
        self.CHANNELS = handshake.body["channels"]
        self.WORD_TYPE = handshake.body["word_type"]
        self.BUFFER_SIZE = handshake.body["buffer_size"]

        self.buffer = np.empty((self.BUFFER_SIZE, self.CHANNELS), dtype=self.WORD_TYPE)

    async def _record_buffer(self):
        loop = asyncio.get_event_loop()
        event = asyncio.Event()
        i = 0

        def callback(indata, frame_count, time_info, status):
            nonlocal i
            if status:
                logging.info(status)

            remainder = len(self.buffer) - i
            if remainder == 0:
                loop.call_soon_threadsafe(event.set)
                raise sd.CallbackStop

            indata = indata[:remainder]
            self.buffer[i:i + len(indata)] = indata
            i += len(indata)

        stream = sd.InputStream(callback=callback, dtype=self.buffer.dtype, channels=self.buffer.shape[1])

        with stream:
            await event.wait()


    async def _play_buffer(self):
        loop = asyncio.get_event_loop()
        event = asyncio.Event()
        i = 0

        def callback(outdata, frame_count, time_info, status):
            nonlocal i
            if status:
                logging.info(status)
            remainder = len(self.buffer) - i
            if remainder == 0:
                loop.call_soon_threadsafe(event.set)
                raise sd.CallbackStop

            valid_frames = frame_count if remainder >= frame_count else remainder
            outdata[:valid_frames] = self.buffer[i:i + valid_frames]
            outdata[valid_frames:] = 0
            i += valid_frames

        stream = sd.OutputStream(callback=callback, dtype=self.buffer.dtype, channels=self.buffer.shape[1])

        with stream:
            await event.wait()
