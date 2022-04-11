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
- **Body length**: 16bit

### Handshake - 0x00:
In BSON format.

#### Client:
**Contains**:
- Display name: "display_name"

#### Server:
**Contains**:
- Sample rate: "sample_rate"
- Channels: "channels"
- Word type: "word_type"
- Buffer size: "buffer_size"

### Sound - 0x01
Raw format

**Contains**:
- ID: "id" (32 bit)
- Sound data: "sound_data"

### Status - 0x02:
In BSON format

**Contains**:
- List of display names: "connected_users"

### Disconnect - 0x03:
**Contains**
- Reason for disconnect: "disconnect_reason"

### Heart beat - 0xff:
**Empty**

