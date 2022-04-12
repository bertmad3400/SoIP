import sounddevice as sd
import numpy as np
from socketserver import DatagramRequestHandler, ThreadingUDPServer
from datetime import datetime, timezone
from queue import Queue
import asyncio
import threading
import logging

from server.options import SoundOptions
from common.packet import Packet, PacketType
from common.options import ProtocolOptions, configure_logging

import os

class ConnectedClient:
    def __init__(self, display_name, socket, address):
        self.display_name = display_name
        self.last_packet = datetime.now(timezone.utc)
        self.audio_parts = Queue()
        self.socket = socket
        self.address = address

    def update_last_packet(self, last_packet=None):
        if last_packet == None:
            last_packet = datetime.now(timezone.utc)
        logging.debug(f"Packet received at {last_packet}")
        self.last_packet = last_packet

class ServerRequestHandler(DatagramRequestHandler):
    def handle(self):
        raw_data = bytearray(self.request[0])
        socket = self.request[1]
        logging.debug(f"Converting packet with size of {len(raw_data)} bytes")
        in_packet = Packet.deserialize(raw_data)
        server.handle_packet(in_packet, socket, self.client_address)       

class Server:
    def __init__(self, listen_address):
        self.listen_address = listen_address

        self.clients = {}
        self.client_lock = threading.Lock()

    def send_packet(self, client: ConnectedClient, packet: Packet):
        logging.info(f"Sending packet ({packet.packet_type}) to {client.address}")
        client.socket.sendto(packet.serialize(), client.address)

    def handle_packet(self, in_packet, socket, client_address):
        self.client_lock.acquire()
        client = self.clients.get(client_address)
        logging.info(f"Handling packet with type {in_packet.packet_type} from client {client_address}.")
        match in_packet.packet_type:
            case PacketType.HANDSHAKE:
                if not client:
                    logging.info(f"New user with display name: {in_packet.body.content['display_name']}")
                    client = ConnectedClient(in_packet.body.content['display_name'], socket, client_address)
                    self.clients[client_address] = client
                logging.info(f"Handshake from client {client}")
                logging.info(f"Current clients {self.clients}")
                print(SoundOptions)
                self.send_packet(client, Packet(PacketType.HANDSHAKE, SoundOptions.as_dict()))
            case PacketType.HEARTBEAT:
                pass # No need to do anything.
            case PacketType.STATUS:
                status = {
                    'connected_users': [c.display_name for c in self.clients]
                }
                self.send_packet(client, Packet(PacketType.STATUS, status))
            case PacketType.SOUND:
                client.audio_parts.put(in_packet.body.content)
            case PacketType.DISCONNECT:
                self.send_packet_to(client, Packet(PacketType.DISCONNECT, None))
        client.update_last_packet()
        self.client_lock.release()

    def process_audio(self):
        while True:
            self.client_lock.acquire()
            for client_address in self.clients:
                client = self.clients[client_address]
                logging.info(f"Audio part count: {client.audio_parts.qsize()}")
                if not client.audio_parts.empty():
                    audio_part = client.audio_parts.get_nowait()
                    logging.info(f"Processing audio for {client.display_name} at {client.address}")
                    for other_client in self.clients:
                        if client == other_client: continue
                        client.socket.sendto(Packet(PacketType.SOUND, { "id" : 0, "sound_data": audio_part }).serialize(), client.add)
            self.client_lock.release()

    def listen(self):
        with ThreadingUDPServer(self.listen_address, ServerRequestHandler) as server:
            server.serve_forever()

    def run(self):
        threads = [
                threading.Thread(target=self.listen, daemon=True),
                threading.Thread(target=self.process_audio, daemon=True)
            ]
        for thread in threads:
            thread.start()

        for thread in threads: thread.join()


if __name__ == "__main__":
    configure_logging()
    server = Server(('127.0.0.1', 3333))
    try:
        server.run()
    except KeyboardInterrupt:
        logging.critical("Interrupted by user.")
        os._exit(1)
