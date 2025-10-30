import struct, zlib

HEADER_FMT = "!BBHIIHHI"  # 20 bytes: ver, flags, conn_id, seq, ack, win, len, checksum

def pack_header(ver, flags, conn_id, seq, ack, win, length, checksum=0):
    return struct.pack(HEADER_FMT, ver, flags, conn_id, seq, ack, win, length, checksum)

def compute_checksum(header_zeroed: bytes, payload: bytes) -> int:
    return zlib.crc32(header_zeroed + payload) & 0xffffffff

def make_packet(ver, flags, conn_id, seq, ack, win, payload: bytes):
    length = len(payload)
    h0 = pack_header(ver, flags, conn_id, seq, ack, win, length, 0)
    chk = compute_checksum(h0, payload)
    return pack_header(ver, flags, conn_id, seq, ack, win, length, chk) + payload

def unpack_packet(packet: bytes):
    header = packet[:20]
    payload = packet[20:]
    ver, flags, conn_id, seq, ack, win, length, chk = struct.unpack(HEADER_FMT, header)
    h0 = pack_header(ver, flags, conn_id, seq, ack, win, length, 0)
    if compute_checksum(h0, payload) != chk:
        raise ValueError("Checksum mismatch")
    return dict(ver=ver, flags=flags, conn_id=conn_id, seq=seq, ack=ack,
                win=win, length=length, checksum=chk), payload
