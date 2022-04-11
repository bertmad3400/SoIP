from common.packet import PacketType, Packet
from common.options import ProtocolOptions

import sounddevice as sd
import numpy as np
import asyncio

import logging

import sys
import socket

from time import sleep
from datetime import datetime, timedelta

from queue import Queue

class Disconnect(Exception):
    pass

class Timeout(Exception):
    pass

class Client:
    def __init__(self, server_ip, server_port, display_name):

        self.server_address = (server_ip, server_port)
        self.sock = socket.socket(type=socket.SOCK_DGRAM)

        self.connected_users = []
        self.display_name = display_name

        self.buffer = np.empty((150_000, 2), dtype="float32")
        self.muted = False
        self.last_sent_time = datetime.now()
        self.last_recieved_time = datetime.now()
        self.packet_id = 0

    def handshake(self):
        self.send_packet(Packet(PacketType.HANDSHAKE, {"display_name" : self.display_name}))

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


    async def play_sound(self, sound):
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
    while True:
        if client.muted:
            if (last_sent_time - datetime.now()) / timedelta(milliseconds=1) > 1000:
                client.send_packet(Packet(PacketType.HEARTBEAT, None))
        else:
            await client.record_buffer()
            client.packet_id += 1
            client.send_pack(Packet(PacketType.SOUND, client.buffer, packet_id=client.packet_id))

async def recieve_packets(client):
    while True:
        if (last_recieved_time - datetime.now()) / timedelta(milliseconds=1) > ProtocolOptions.TIMEOUT:
            raise Timeout

        packet = client.recieve_packet()

        if packet:
            match packet.packet_type:
                case PacketType.STATUS:
                    client.connected_users = packet.body["connected_users"]
                case PacketType.DISCONNECT:
                    raise Disconnect(packet.body["disconnect_reason"])
                case PacketType.SOUND:
                    sound_queue.put_nowait((packet.body["id"], packet.body["sound_data"]))

async def play_sound_queue(client, sound_queue):
    while True:
        if not sound_queue.empty():
            client.play_sound(sound_queue.get_nowait()[1])


async def main():
    client = Client("127.0.0.1", 3333)

    while True:
        try:
            client.handshake()
            break
        except Exception as e:
            logging.error(f'Encountered following error when attempting handshake: "{e}". Trying again')
            sleep(1)

    sound_queue = Queue()

    send_packets_task = asyncio.create_task(send_packets(client))
    recieve_packets_task = asyncio.create_task(recieve_packets(client, sound_queue))
    play_sound_task = asyncio.create_task(play_sound_queue(client, sound_queue))

    await recieve_packets_task
    await send_packets_task
    await play_sound_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit('\nInterrupted by user')
    except Disconnect as reason:
        sys.exit(f"\nServer disconnected. Reason: {reason}")
    except Timeout:
        sys.exit("\nConnection to server timed out.")
