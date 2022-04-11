from enum import Enum

class PacketType(Enum):
    HANDSHAKE = 0x00
    SOUND = 0x01
    STATUS = 0x02
    HEARTBEAT = 0xfe
    DISCONNECT = 0xff

class Packet():
    PROTOCOL_MAGIC_NUMBER = 0x69
    def __init__(self, packet_type, body):
        self.magic_number = PROTOCOL_MAGIC_NUMBER
        self.packet_type = packet_type
        #self.checksum = checksum
        self.body = body

    # Serialize into datagram body
    def serialize(self):
        bs = bytearray()
        bs.append(self.magic_number)
        bs.append(self.packet_type)
        bs.extend(body)

    # Deserialize from datagram body
    def deserialize(bytes: bytearray):
        magic_number = bytes.pop(0)
        packet_type = bytes.pop(0)
        body = bytes
        assert magic_number == PROTOCOL_MAGIC_NUMBER
        return Packet(packet_type, body)
