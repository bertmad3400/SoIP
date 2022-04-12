import sounddevice as sd
import numpy as np
from socketserver import DatagramRequestHandler, ThreadingUDPServer
from datetime import datetime, timezone
from queue import Queue
import asyncio

from server.options import SoundOptions
from common.packet import Packet, PacketType
from common.options import ProtocolOptions

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
        self.last_packet = last_packet

class ServerRequestHandler(DatagramRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        in_packet = Packet.deserialize(bytearray(data))
        server.handle_packet(in_packet, socket, self.client_address)       

class Server:
    def __init__(self, listen_address):
        self.listen_address = listen_address

        print(SoundOptions.SAMPLE_RATE)

        self.clients = {}


    def handle_packet(self, in_packet, socket, client_address):
        client = self.clients.get(client_address)
        match in_packet.packet_type:
            case PacketType.HANDSHAKE:
                if not client:
                    client = ConnectedClient(in_packet.body.content['display_name'], socket, client_address)
                    self.clients[client_address] = client

                print(SoundOptions)
                out_packet = Packet(PacketType.HANDSHAKE, SoundOptions.as_dict())
                socket.sendto(out_packet.serialize(), client_address)
            case PacketType.HEARTBEAT:
                pass # No need to do anything.
            case PacketType.STATUS:
                status = {
                    'connected_users': [c.display_name for c in self.clients]
                }
                out_packet = Packet(PacketType.STATUS, status)
                socket.sendto(out_packet.serialize(), client_address)
            case PacketType.SOUND:
                client.audio_parts.put(in_packet.body.content)
            case PacketType.DISCONNECT:
                out_packet = Packet(PacketType.DISCONNECT, None)
                socket.sendto(out_packet.serialize(), client_address)
        client.update_last_packet()

    async def process_audio(self):
        while True:
            for client in self.clients:
                audio_part = client.audio_parts.get()
                for other_client in clients:
                    if client == other_client: continue
                    client.socker.sendto(Packet(PacketType.SOUND, audio_part).serialize(), client.add)

    async def listen(self):
        with ThreadingUDPServer(self.listen_address, ServerRequestHandler) as server:
            audio_task = asyncio.create_task(self.process_audio())
            server.serve_forever()
            await audio_task

if __name__ == "__main__":
    server = Server(('127.0.0.1', 3333))
    asyncio.run(server.listen())
