import sounddevice as sd
import numpy as np
from socketserver import DatagramRequestHandler, ThreadingUDPServer
from datetime import datetime, timezone
from queue import PriorityQueue
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
        self.audio_parts = PriorityQueue()
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
        logging.info(f"Sending packet ({packet.packet_type.name}) to {client.address}")
        client.socket.sendto(packet.serialize(), client.address)

    def handle_packet(self, in_packet, socket, client_address):
        self.client_lock.acquire()
        client = self.clients.get(client_address)
        logging.info(f"Handling packet with type {in_packet.packet_type.name} from client {client_address}.")
        match in_packet.packet_type:
            case PacketType.HANDSHAKE:
                if not client:
                    logging.info(f"New user with display name: {in_packet.body.content['display_name']}")
                    client = ConnectedClient(in_packet.body.content['display_name'], socket, client_address)
                    self.clients[client_address] = client
                logging.info(f"Handshake from client {client.address}")
                logging.info(f"Current clients {list(self.clients.keys())}")
                self.send_packet(client, Packet(PacketType.HANDSHAKE, SoundOptions.as_dict()))
            case PacketType.HEARTBEAT:
                pass # No need to do anything.
            case PacketType.STATUS:
                status = {
                    'connected_users': [c.display_name for c in self.clients]
                }
                self.send_packet(client, Packet(PacketType.STATUS, status))
            case PacketType.SOUND:
                client.audio_parts.put((in_packet.body.content["id"], in_packet.body.content["sound_data"]))
            case PacketType.DISCONNECT:
                self.send_packet(client, Packet(PacketType.DISCONNECT, None))
        client.update_last_packet()
        self.client_lock.release()

    def process_audio(self):
        audioID = 0

        while True:
            self.client_lock.acquire()

            audio_fragments = {}

            for client_address in self.clients:
                client = self.clients[client_address]
                if not client.audio_parts.empty():
                    logging.info(f"Processing audio for {client.display_name} at {client.address}")
                    audio_fragments[client_address] = client.audio_parts.get_nowait()[1]

            self.client_lock.release()

            if audio_fragments:
                audioID += 1

                for client_address in audio_fragments:
                    if len(audio_fragments) == 1 and client_address in audio_fragments:
                        continue

                    current_client_fragments = [fragment * (2/3) for address, fragment in audio_fragments.items() if address != client_address]
                    current_client_sound = sum(current_client_fragments)

                    audio_packet = Packet(PacketType.SOUND, current_client_sound, audioID)
                    print("ho")
                    self.send_packet(self.clients[client_address], audio_packet)


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
