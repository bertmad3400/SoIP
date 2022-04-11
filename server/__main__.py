import sounddevice as sd
import numpy as np
from socketserver import DatagramRequestHandler, UDPServer
from datetime import datetime, timezone

from server.options import SoundOptions
from common.packet import Packet, PacketType
from common.options import ProtocolOptions

class ConnectedClient:
    def __init__(self, display_name):
        self.display_name = display_name
        self.last_packet = datetime.now(timezone.utc)


    def update_last_packet(last_packet=None):
        if last_packet == None:
            last_packet = datetime.now(timezone.utc)
        self.last_packet = last_packet

class ServerRequestHandler(DatagramRequestHandler):
    def __init__(self, server):
        self.server = server # this refers to the other classes thing (pass by reference)

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

        self.request_handler = ServerRequestHandler(self)

    def handle_packet(self, in_packet, socket, client_address):
        client = clients.get(client_address)
        match in_packet.packet_type:
            case PacketType.HANDSHAKE:
                if not client:
                    client = ConnectedClient(in_packet.body['display_name'])
                    clients[client_address] = client
                out_packet = Packet(PacketType.HANDSHAKE, dict(SoundOptions))
                socket.sendto(out_packet.serialize(), client_address)
            case PacketType.HEARTBEAT:
                pass # No need to do anything.
            case PacketType.STATUS:
                status = {
                    'connected_users': [c.display_name for c in clients]
                }
                out_packet = Packet(PacketType.STATUS, status)
                socket.sendto(out_packet.serialize(), client_address)
            case PacketType.SOUND:
                raise NotImplemented("TODO")
                out_packet = Packet(PacketType.SOUND, None)
                socket.sendto(out_packet.serialize(), client_address)
            case PacketType.DISCONNECT:
                out_packet = Packet(PacketType.DISCONNECT, None)
                socket.sendto(out_packet.serialize(), client_address)
        client.update_last_packet()

    def listen(self):
        with UDPServer(self.listen_address, self.request_handler) as server:
            server.serve_forever()

if __name__ == "__main__":
    server = Server(('127.0.0.1', 3333))
    server.listen()
