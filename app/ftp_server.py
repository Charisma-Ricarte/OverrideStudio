# app/ftp_server.py
import asyncio
import os
import zlib
from typing import Optional

from transport.transport import GBNTransport
from app.fileops import save_chunks, CHUNK_SIZE

SERVER_DIR = "server_files"
os.makedirs(SERVER_DIR, exist_ok=True)

CMD_FLAG = 0x01
HDR_PREFIX = b"HDR "  # explicit binary-safe header for data frames

class ClientState:
    def __init__(self):
        self.cmd_buf = bytearray()
        self.uploading = False
        self.upload_fname: Optional[str] = None
        self.upload_chunks = []
        self.expected_size = 0
        self.received_size = 0
        self.partial = bytearray()
        self.expecting_header = True
        self.current_expected_len = 0
        self.current_expected_crc = None

def is_control_text(payload: bytes) -> bool:
    """
    Minimal control-text heuristic: has newline and starts with known token.
    We'll still prefer explicit flags + control packets, but this helps robustness.
    """
    if not payload or b"\n" not in payload:
        return False
    try:
        s = payload.decode("utf-8", errors="ignore")
    except Exception:
        return False
    first = s.split()[0].upper() if s.split() else ""
    return first in {"LIST", "DELETE", "GET", "PUT", "DONE", "OFFSET", "OK", "NOTFOUND", "ERROR", "CRCERR"}

class FTPServer:
    def __init__(self, proto: GBNTransport):
        self.proto = proto
        self.state = ClientState()

    def send_control(self, text: str):
        self.proto.send_control(text.encode())

    def on_receive(self, hdr, payload: bytes):
        st = self.state

        # If flagged as control and looks like control text -> process commands
        if hdr and (hdr.get("flags", 0) & CMD_FLAG) and is_control_text(payload):
            st.cmd_buf.extend(payload)
            while True:
                if b"\n" not in st.cmd_buf:
                    break
                idx = st.cmd_buf.index(b"\n")
                line = bytes(st.cmd_buf[:idx]).decode(errors="ignore").strip()
                del st.cmd_buf[: idx + 1]
                if not line:
                    continue
                parts = line.split()
                cmd = parts[0].upper()
                if cmd == "LIST":
                    files = os.listdir(SERVER_DIR)
                    out = ("\n".join(files) + "\nEND\n") if files else "\nEND\n"
                    self.send_control(out)
                    continue
                if cmd == "DELETE" and len(parts) == 2:
                    name = parts[1]
                    p = os.path.join(SERVER_DIR, name)
                    if os.path.exists(p):
                        os.remove(p)
                        self.send_control("OK\nEND\n")
                    else:
                        self.send_control("NOTFOUND\nEND\n")
                    continue
                if cmd == "GET" and len(parts) >= 2:
                    name = parts[1]
                    offset = int(parts[2]) if len(parts) >= 3 else 0
                    p = os.path.join(SERVER_DIR, name)
                    if not os.path.exists(p):
                        self.send_control("NOTFOUND\nEND\n")
                        continue
                    with open(p, "rb") as f:
                        f.seek(offset)
                        while True:
                            piece = f.read(CHUNK_SIZE)
                            if not piece:
                                break
                            crc = zlib.crc32(piece) & 0xFFFFFFFF
                            hdr = HDR_PREFIX + f"{crc} {len(piece)}\n".encode()
                            self.proto.send(hdr + piece)
                    self.send_control("DONE\nEND\n")
                    continue
                if cmd == "PUT" and len(parts) >= 2:
                    name = parts[1]
                    size = int(parts[2]) if len(parts) >= 3 else 0
                    p = os.path.join(SERVER_DIR, name)
                    st.uploading = True
                    st.upload_fname = p
                    st.upload_chunks = []
                    st.expected_size = size
                    st.received_size = 0
                    st.partial = bytearray()
                    st.expecting_header = True
                    st.current_expected_len = 0
                    st.current_expected_crc = None
                    offset = os.path.getsize(p) if os.path.exists(p) else 0
                    self.send_control(f"OFFSET {offset}\nEND\n")
                    continue
                if cmd == "DONE":
                    if not st.uploading:
                        self.send_control("ERROR no PUT\nEND\n")
                        continue
                    save_chunks(st.upload_fname, [(b, 0) for b, _ in st.upload_chunks])
                    st.uploading = False
                    st.upload_fname = None
                    st.upload_chunks = []
                    st.expected_size = 0
                    st.received_size = 0
                    st.partial = bytearray()
                    st.expecting_header = True
                    st.current_expected_len = 0
                    st.current_expected_crc = None
                    self.send_control("OK\nEND\n")
                    continue
                self.send_control("ERROR unknown\nEND\n")
            return

        # Otherwise treat the payload as data (or misflagged control)
        # Data frames MUST be framed with HDR_PREFIX header (binary-safe)
        if st.uploading:
            st.partial.extend(payload)
            while True:
                if st.expecting_header:
                    # look for HDR_PREFIX at start
                    if len(st.partial) < len(HDR_PREFIX):
                        return
                    # If not starting with HDR_PREFIX, try to find it
                    if not st.partial.startswith(HDR_PREFIX):
                        # find occurrence of HDR_PREFIX later; if none, wait for more bytes
                        idx = st.partial.find(HDR_PREFIX)
                        if idx == -1:
                            # maybe partial data; don't drop yet
                            return
                        # drop earlier garbage bytes before HDR (robust recovery)
                        del st.partial[:idx]
                        if len(st.partial) < len(HDR_PREFIX):
                            return
                    # now we have HDR_PREFIX at start; find newline
                    if b"\n" not in st.partial:
                        return
                    idx_new = st.partial.index(b"\n")
                    header = bytes(st.partial[:idx_new]).decode(errors="ignore").strip()
                    del st.partial[: idx_new + 1]
                    # header format: HDR <crc> <len>
                    parts = header.split()
                    if len(parts) != 3 or parts[0] != "HDR":
                        self.send_control("ERROR bad DATA\nEND\n")
                        st.uploading = False
                        st.partial.clear()
                        return
                    try:
                        crc_recv = int(parts[1])
                        length = int(parts[2])
                    except Exception:
                        self.send_control("ERROR bad DATA header\nEND\n")
                        st.uploading = False
                        st.partial.clear()
                        return
                    st.current_expected_crc = crc_recv
                    st.current_expected_len = length
                    st.expecting_header = False
                if not st.expecting_header:
                    if len(st.partial) < st.current_expected_len:
                        return
                    chunk = bytes(st.partial[: st.current_expected_len])
                    del st.partial[: st.current_expected_len]
                    calc = zlib.crc32(chunk) & 0xFFFFFFFF
                    if calc != st.current_expected_crc:
                        self.send_control("CRCERR\nEND\n")
                        st.expecting_header = True
                        st.current_expected_crc = None
                        st.current_expected_len = 0
                        continue
                    st.upload_chunks.append((chunk, st.current_expected_crc))
                    st.received_size += len(chunk)
                    st.expecting_header = True
                    st.current_expected_crc = None
                    st.current_expected_len = 0
                    if st.expected_size and st.received_size >= st.expected_size:
                        return
                    continue

        # ignore stray data otherwise
        return

async def main():
    print("[Server] Starting...")
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: GBNTransport(local_port=9000),
        local_addr=("0.0.0.0", 9000),
    )
    server = FTPServer(protocol)
    protocol.set_callback(server.on_receive)
    print("[Server] Running on port 9000")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
