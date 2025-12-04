# transport/header.py
import struct

HDR_FMT = '!4sBIII'
HDR_SIZE = struct.calcsize(HDR_FMT)

def make_packet(magic_tag, flags, conn_id, seq, ack, length, payload: bytes):
    """
    Build packet: magic(4), flags(1), conn_id(4), seq(4), ack(4) + payload
    """
    return struct.pack(HDR_FMT, b'MFTP', flags, conn_id, seq & 0xffffffff, ack & 0xffffffff) + payload

def unpack_packet(data: bytes):
    """Return (hdr_dict, payload). Raises ValueError if too small."""
    if len(data) < HDR_SIZE:
        raise ValueError("Packet too small")
    hdr_raw = data[:HDR_SIZE]
    payload = data[HDR_SIZE:]
    magic, flags, conn_id, seq, ack = struct.unpack(HDR_FMT, hdr_raw)
    return {"magic": magic, "flags": flags, "conn_id": conn_id, "seq": seq, "ack": ack}, payload
