from common.packet import PacketType, Packet
from common.options import ProtocolOptions, configure_logging

import sounddevice as sd
import numpy as np
import threading
import asyncio

import json
import logging

import os
import sys
import socket

from time import sleep
from datetime import datetime, timedelta

from queue import PriorityQueue

class Disconnect(Exception):
    pass

class Timeout(Exception):
    pass

class WrongPacket(Exception):
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
        logging.info("Sending handshake")
        self.send_packet(Packet(PacketType.HANDSHAKE, {"display_name" : self.display_name}))

        logging.debug("Waiting on handshake response...")
        self.last_recieved_time = datetime.now()
        while True:
            if (datetime.now() - self.last_recieved_time) / timedelta(milliseconds=1) > ProtocolOptions.TIMEOUT:
                raise Timeout("Timed out waiting for handshake response.")
            handshake = self.recieve_packet()

            if handshake and handshake.packet_type == PacketType.HANDSHAKE:
                logging.info(f"Recieved handshake, with following options: {json.dumps(handshake.body.content)}.")
                break
            elif handshake:
                raise WrongPacket("Recieved packet, but it wasn't a handshake.")


        self.SAMPLE_RATE = handshake.body.content["sample_rate"]
        self.CHANNELS = handshake.body.content["channels"]
        self.WORD_TYPE = handshake.body.content["word_type"]
        self.BUFFER_SIZE = handshake.body.content["buffer_size"]

        self.buffer = np.empty((self.BUFFER_SIZE, self.CHANNELS), dtype=self.WORD_TYPE)

    def send_packet(self, packet):
        raw_packet = packet.serialize()
        logging.debug(f"Sending packet of type {packet.packet_type.name} and size {len(raw_packet)} bytes")
        self.last_sent_time = datetime.now()
        self.sock.sendto(raw_packet, self.server_address)

    def recieve_packet(self):
        try:
            raw_data = bytearray(self.sock.recv(65536, socket.MSG_DONTWAIT))

            if len(raw_data) == 0:
                return None

            logging.debug(f"Recieved packet of size {len(raw_data)} bytes")
            last_recieved_time = datetime.now()
            packet = Packet.deserialize(raw_data)
            logging.debug(f"Recieved packet of type {packet.packet_type.name}")
            return packet
        except BlockingIOError:
            return None

    def record_buffer(self):
        logging.debug("Recording to buffer...")
        i = 0

        def callback(indata, frame_count, time_info, status):
            nonlocal i
            if status:
                logging.info(status)

            remainder = len(self.buffer) - i
            if remainder == 0:
                raise sd.CallbackStop

            indata = indata[:remainder]
            self.buffer[i:i + len(indata)] = indata
            i += len(indata)

        stream = sd.InputStream(callback=callback, dtype=self.buffer.dtype, channels=self.buffer.shape[1])

        with stream:
            logging.debug("Finished recording to buffer.")


    def play_sound(self, sound):
        logging.debug("Playing sound...")
        i = 0

        def callback(outdata, frame_count, time_info, status):
            nonlocal i
            if status:
                logging.info(status)
            remainder = len(sound) - i
            if remainder == 0:
                raise sd.CallbackStop

            valid_frames = frame_count if remainder >= frame_count else remainder
            outdata[:valid_frames] = sound[i:i + valid_frames]
            outdata[valid_frames:] = 0
            i += valid_frames

        stream = sd.OutputStream(callback=callback, dtype=sound.dtype, channels=sound.shape[1])

        with stream:
            logging.debug("Finished playing sound.")

def send_packets(client):
    while True:
        if client.muted:
            if (last_sent_time - datetime.now()) / timedelta(milliseconds=1) > 1000:
                client.send_packet(Packet(PacketType.HEARTBEAT, None))
        else:
            client.record_buffer()
            client.packet_id += 1
            client.send_packet(Packet(PacketType.SOUND, client.buffer, packet_id=client.packet_id))

def recieve_packets(client, sound_queue):
    while True:
        if (datetime.now() - client.last_recieved_time) / timedelta(milliseconds=1) > ProtocolOptions.TIMEOUT:
            raise Timeout

        packet = client.recieve_packet()

        if packet:
            logging.info("Recived package")
            match packet.packet_type:
                case PacketType.STATUS:
                    client.connected_users = packet.body.content["connected_users"]
                case PacketType.DISCONNECT:
                    raise Disconnect(packet.body.content["disconnect_reason"])
                case PacketType.SOUND:
                    sound_queue.put_nowait((packet.body.content["id"], packet.body.content["sound_data"]))

def play_sound_queue(client, sound_queue):
    while True:
        if not sound_queue.empty():
            logging.info("Playing new sound.")
            client.play_sound(sound_queue.get_nowait()[1])


def main():
    client = Client("127.0.0.1", 3333, "Hest")
    logging.info("Created client.")

    client.handshake()

    sound_queue = PriorityQueue()

    threads = {}

    threads["send_packets_thread"] = threading.Thread(target=send_packets, args=(client,), daemon=True)
    threads["recieve_packets_thread"] = threading.Thread(target=recieve_packets, args=(client, sound_queue), daemon=True)
    threads["play_sound_thread"] = threading.Thread(target=play_sound_queue, args=(client, sound_queue), daemon=True)

    for thread_name in threads:
        threads[thread_name].start()

    for thread_name in threads:
        threads[thread_name].join()

if __name__ == "__main__":
    configure_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.critical("Interrupted by user")
        os._exit(1)
    except Disconnect as reason:
        logging.critical(f"Server disconnected. Reason: {reason}")
        os._exit(1)
    except Timeout:
        logging.critical("Connection to server timed out.")
        os._exit(1)
