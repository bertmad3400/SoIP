import sounddevice as sd
import numpy as np
from socketserver import DatagramRequestHandler, UDPServer

from common import options

class ServerRequestHandler(DatagramRequestHandler):
    def __init__(self, clients):
        self.clients = clients # this refers to the other classes thing (pass by reference)

    def handle(self):
        data = self.request[0]
        socket = self.request[1]

class Server:
    def __init__(self, listen_address):
        self.listen_address = listen_address

        print(options.SoundOptions.SAMPLE_RATE)

        self.clients = []

        self.request_handler = ServerRequestHandler(self.clients)

    def listen(self):
        with UDPServer(self.listen_address, self.request_handler) as server:
            server.serve_forever()

if __name__ == "__main__":
    server = Server(('127.0.0.1', 3333))
    server.listen()
