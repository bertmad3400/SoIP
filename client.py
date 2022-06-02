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

from queue import PriorityQueue, Queue

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
            self.last_recieved_time = datetime.now()
            packet = Packet.deserialize(raw_data)
            logging.debug(f"Recieved packet of type {packet.packet_type.name}")
            return packet
        except BlockingIOError:
            return None

def send_packets(client, sound_queue):
    while True:
        if client.muted or sound_queue.empty():
            if (client.last_sent_time - datetime.now()) / timedelta(milliseconds=1) > 1000:
                client.send_packet(Packet(PacketType.HEARTBEAT, None))
        else:
            client.packet_id += 1
            client.send_packet(Packet(PacketType.SOUND, sound_queue.get_nowait(), packet_id=client.packet_id))

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
                    logging.info("Updated connected-user-list. Currently looks like:\n" + " --- ".join(client.connected_users))
                case PacketType.DISCONNECT:
                    raise Disconnect(packet.body.content["disconnect_reason"])
                case PacketType.SOUND:
                    sound_queue.put_nowait((packet.body.content["id"], packet.body.content["sound_data"]))

class AudioSupplier:
    def __init__(self, queue):
        self.queue = queue
        self.current_fragment = None
        self.current_fragment_index = 0

    def _get_empty_frames(frame_count):
        return np.empty(frame_count)

    def get_frames(self, frame_count):
        if frame_count == 0:
            return np.empty(0)
        if self.current_fragment == None:
            if self.queue.empty():
                return AudioSupplier._get_empty_frames(frame_count)
            else:
                current_fragment = self.queue.get_nowait()[1].reshape(-1)
                current_fragment_index = 0
        remainding_frames_in_fragment = len(current_fragment) - current_fragment_index
        if remainding_frames_in_fragment == 0:
            current_fragment = None
            return self.get_frames(frame_count)

        outdata = np.empty(frame_count)
        frames_to_write_from_current_fragment = min(frame_count, remainding_frames_in_fragment)
        outdata[:frames_to_write_from_current_fragment] = current_fragment[current_fragment_index:current_fragment_index+frames_to_write_from_current_fragment]
        current_fragment_index += frames_to_write_from_current_fragment
        outdata[frames_to_write_from_current_fragment:] = self.get_frames(frame_count - frames_to_write_from_current_fragment)

        return outdata

def handle_sound(client, input_sound_queue, output_sound_queue):
    supplier = AudioSupplier(output_sound_queue)
    def callback(indata, outdata, frame_count, time_info, status):
        input_sound_queue.put(indata.copy())
        outdata[:] = supplier.get_frames(frame_count).reshape(-1, 1)
    with sd.Stream(samplerate=client.SAMPLE_RATE, channels=client.CHANNELS, dtype=client.WORD_TYPE, callback=callback):
        while True: sleep(10)
    os._exit(1)

def main():
    name = "Anonym"
    if len(sys.argv) > 2:
        name = sys.argv[1]
    server_address = "127.0.0.1"
    if len(sys.argv) > 3:
        server_address = sys.argv[2]
    client = Client(server_address, 3333, name)
    logging.info("Created client.")

    client.handshake()

    output_sound_queue = PriorityQueue()
    input_sound_queue = Queue()

    threads = {}

    threads["send_packets_thread"] = threading.Thread(target=send_packets, args=(client, input_sound_queue), daemon=True)
    threads["recieve_packets_thread"] = threading.Thread(target=recieve_packets, args=(client, output_sound_queue), daemon=True)
    threads["play_sound_thread"] = threading.Thread(target=handle_sound, args=(client, input_sound_queue, output_sound_queue), daemon=True)

    for thread_name in threads:
        threads[thread_name].start()

    for thread_name in threads:
        threads[thread_name].join()

if __name__ == "__main__":
    configure_logging()
    try:
        main()
    except KeyboardInterrupt:
        logging.critical("Interrupted by user")
        os._exit(1)
    except Disconnect as reason:
        logging.critical(f"Server disconnected. Reason: {reason}")
        os._exit(2)
    except Timeout:
        logging.critical("Connection to server timed out.")
        os._exit(3)
