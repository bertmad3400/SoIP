# Protocol specification for SoIP

## Packet specification:

### Types:
Client- and serverbound:
- Handshake
- Sound
- Heart beat
- Disconnect

Clientbound:
- Status

### Packet header:

- **Magic number**: 8 bit
- **Packet type**: 8 bit
- **CRC checksum**: 32bit
- **Body length**: 32bit

### Handshake - 0x00:
In BSON format.

#### Client:
**Contains**:
- Display name

#### Server:
**Contains**:
- Sample rate
- Channels
- Word type

### Sound - 0x01
Raw format

**Contains**:
- Sound data

### Status - 0x02:
In BSON format

**Contains**:
- List of display names


### Heart beat - 0xfe:
**Empty**

### Disconnect - 0xff:
**Empty**

