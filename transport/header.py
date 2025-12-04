# transport/header.py
import struct

HDR_FMT = '!4sBIII'
HDR_SIZE = struct.calcsize(HDR_FMT)

def make_packet(magic_tag, flags, conn_id, seq, ack, length, payload: bytes):
    return struct.pack(HDR_FMT, b'MFTP', flags, conn_id, seq & 0xffffffff, ack & 0xffffffff) + payload

def unpack_packet(data: bytes):
    if len(data) < HDR_SIZE:
        raise ValueError("Packet too small")
    hdr_raw = data[:HDR_SIZE]
    payload = data[HDR_SIZE:]
    magic, flags, conn_id, seq, ack = struct.unpack(HDR_FMT, hdr_raw)
    return {
        "magic": magic,
        "flags": flags,
        "conn_id": conn_id,
        "seq": seq,
        "ack": ack
    }, payload
