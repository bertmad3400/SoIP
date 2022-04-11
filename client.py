from common import *

import sounddevice as sd
import numpy as np
import asyncio

import logging

import socket

from time import sleep

class Client:
    def __init__(self, server_ip, server_port):

        self.server_address = (server_ip, server_port)
        self.sock = socket.socket(type=socket.SOCK_DGRAM)

        self.connected_users = {}
        self.buffer = np.empty((150_000, 2), dtype="float32")

    def handshake(self):

        self.send_packet(packet.Packet())

        sleep(1)

        handshake = self.recieve_packet()

        self.SAMPLE_RATE = handshake.body["sample_rate"]
        self.CHANNELS = handshake.body["channels"]
        self.WORD_TYPE = handshake.body["word_type"]
        self.BUFFER_SIZE = handshake.body["buffer_size"]

        self.buffer = np.empty((self.BUFFER_SIZE, self.CHANNELS), dtype=self.WORD_TYPE)

    def send_packet(packet):
        self.last_sent_time = datetime.now()
        self.sock.sendto(packet.seralize(), self.server_address)

    def recieve_packet():
        raw_data = sock.recv(65536)

        if raw_data:
            last_recieved_time = datetime.time()
            return Packet.unserialize(raw_data)

    async def record_buffer(self):
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


    async def _play_sound(self, sound):
        loop = asyncio.get_event_loop()
        event = asyncio.Event()
        i = 0

        def callback(outdata, frame_count, time_info, status):
            nonlocal i
            if status:
                logging.info(status)
            remainder = len(sound) - i
            if remainder == 0:
                loop.call_soon_threadsafe(event.set)
                raise sd.CallbackStop

            valid_frames = frame_count if remainder >= frame_count else remainder
            outdata[:valid_frames] = sound[i:i + valid_frames]
            outdata[valid_frames:] = 0
            i += valid_frames

        stream = sd.OutputStream(callback=callback, dtype=sound.dtype, channels=sound.shape[1])

        with stream:
            await event.wait()

async def send_packets(client):
    pass

async def recieve_packets(client):
    pass

async def main():
    client = Client("127.0.0.1", 3333)

    while True:
        try:
            client.handshake()
        except Exception as e:
            logging.error(f'Encountered following error when attempting handshake: "{e}". Trying again')
            sleep(1)

    recieve_packets_task = asyncio.create_task(recieve_packets(client))
    send_packets_task = asyncio.create_task(send_packets(client))

    await recieve_packets_task
    await send_packets_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit('\nInterrupted by user')
