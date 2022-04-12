import bson
import numpy as np
from io import BytesIO
from enum import IntEnum, unique

@unique
class PacketType(IntEnum):
    HANDSHAKE = 0x00
    SOUND = 0x01
    STATUS = 0x02
    DISCONNECT = 0x03
    HEARTBEAT = 0xff

class Body():
    def __init__(self, content, packet_type):
        self.content = content
        self.packet_type = packet_type

    def serialize(self):
        if self.packet_type in {PacketType.HANDSHAKE, PacketType.STATUS, PacketType.DISCONNECT}:
            return bson.dumps(self.content)
        elif self.packet_type == PacketType.SOUND:
            np_bytes = BytesIO()
            np.save(np_bytes, self.content["sound_data"], allow_pickle=True)
            raw_content = bytearray(self.content["id"].to_bytes(length=4, byteorder="little"))
            raw_content.extend(bytearray(np_bytes.getvalue()))
            return raw_content

    def deserialize(raw_content: bytearray, packet_type):
        if packet_type in {PacketType.HANDSHAKE, PacketType.STATUS, PacketType.DISCONNECT}:
            return Body(bson.loads(raw_content), packet_type)
        elif packet_type == PacketType.SOUND:
            body_dict = { "id" : int.from_bytes(raw_content[:4], byteorder="little"),
                          "sound_data": np.load(BytesIO(raw_content[4:]), allow_pickle=True) }
            return Body(body_dict, packet_type)
        else:
            return None

class Packet():
    PROTOCOL_MAGIC_NUMBER = 0x69
    def __init__(self, packet_type, body, packet_id=None):
        self.magic_number = Packet.PROTOCOL_MAGIC_NUMBER
        self.packet_type = packet_type
        #self.checksum = checksum
        if isinstance(body, Body):
            self.body = body
        elif packet_type == PacketType.SOUND:
            body = {"id" : packet_id, "sound_data": body}
            self.body = Body(body, packet_type)
        else:
            self.body = Body(body, packet_type)

    # Serialize into datagram body
    def serialize(self):
        bs = bytearray()
        bs.extend(self.magic_number.to_bytes(length=1, byteorder="little"))
        bs.extend(int(self.packet_type).to_bytes(length=1, byteorder="little"))

        if self.packet_type in {PacketType.HANDSHAKE, PacketType.STATUS, PacketType.DISCONNECT, PacketType.SOUND}:
            bs.extend(bytearray(self.body.serialize()))

        return bs

    # Deserialize from datagram body
    def deserialize(raw_packet: bytearray):
        magic_number = raw_packet.pop(0)
        packet_type = PacketType(raw_packet.pop(0))
        body = Body.deserialize(raw_packet, packet_type)

        assert magic_number == Packet.PROTOCOL_MAGIC_NUMBER
        return Packet(packet_type, body)
