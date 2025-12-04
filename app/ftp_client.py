# app/ftp_client.py
import asyncio
import os
import zlib
from typing import Optional

from transport.transport import GBNTransport
from app.fileops import iter_chunks, save_chunks, count_chunks, CHUNK_SIZE

SERVER_ADDR = ("127.0.0.1", 9000)
CMD_FLAG = 0x01
HDR_PREFIX = b"HDR "

class FTPClient:
    def __init__(self, loss_rate: float = 0.0):
        self.loss_rate = loss_rate
        self.transport: Optional[GBNTransport] = None
        self.connected = False
        self.on_progress = None  # synchronous callback(done, total)

    async def start(self):
        if self.connected:
            return
        loop = asyncio.get_event_loop()
        trans, proto = await loop.create_datagram_endpoint(
            lambda: GBNTransport(local_port=0, remote_addr=SERVER_ADDR),
            local_addr=("0.0.0.0", 0),
        )
        self.transport = proto
        self.connected = True
        print("[Client] Connected")

    def _set_recv_cb(self, cb):
        if not self.transport:
            raise RuntimeError("Transport not initialized")
        self.transport.clear_callbacks()
        self.transport.set_callback(cb)

    async def send_command(self, text: str):
        if not text.endswith("\n"):
            text = text + "\n"
        self.transport.send_control(text.encode())

    async def recv_response(self):
        buf = bytearray()
        fut = asyncio.get_event_loop().create_future()
        def cb(hdr, chunk):
            if hdr is None:
                return
            if not (hdr.get("flags", 0) & CMD_FLAG):
                return
            nonlocal buf
            buf.extend(chunk)
            if b"END\n" in buf:
                if not fut.done():
                    fut.set_result(bytes(buf))
        self._set_recv_cb(cb)
        resp = await fut
        resp = resp.replace(b"END\n", b"")
        return resp.decode(errors="ignore")

    async def list_files(self):
        await self.send_command("LIST")
        resp = await self.recv_response()
        return [x for x in resp.split("\n") if x.strip()]

    async def delete_file(self, name: str):
        await self.send_command(f"DELETE {name}")
        resp = await self.recv_response()
        return resp.strip() == "OK"

    async def put_file(self, local_path: str, remote_name: str, resume: bool = True):
        """
        Upload a file. Each data chunk is sent as: HDR <crc> <len>\n + payload
        """
        size = os.path.getsize(local_path)
        await self.send_command(f"PUT {remote_name} {size}")
        resp = await self.recv_response()
        parts = resp.strip().split()
        offset = int(parts[1]) if parts and parts[0] == "OFFSET" and len(parts) >= 2 else 0

        chunks = list(iter_chunks(local_path, start_offset=offset))
        total = len(chunks)
        done = 0

        for off, data, crc in chunks:
            hdr = HDR_PREFIX + f"{crc} {len(data)}\n".encode()
            # send header+data as raw bytes; transport will packetize
            self.transport.send(hdr + data)
            done += 1
            if callable(self.on_progress):
                try:
                    self.on_progress(done, total)
                except Exception:
                    pass

        # send DONE control
        self.transport.send_control(b"DONE\n")
        final = await self.recv_response()
        return final.strip()

    async def get_file(self, remote_name: str, local_path: str, resume: bool = True):
        """
        Download file and save to local_path. Prompts for Save As in GUI layer.
        Reassembles HDR-prefixed chunks.
        """
        offset = os.path.getsize(local_path) if resume and os.path.exists(local_path) else 0
        await self.send_command(f"GET {remote_name} {offset}")

        fut = asyncio.get_event_loop().create_future()
        partial = bytearray()
        chunks = []
        done_flag = {"done": False}

        def cb(hdr, chunk):
            # control reply (DONE/NOTFOUND) will come as control flagged packet
            if hdr and (hdr.get("flags", 0) & CMD_FLAG):
                text = chunk.decode(errors="ignore")
                if text.strip().startswith("NOTFOUND"):
                    if not fut.done():
                        fut.set_exception(FileNotFoundError(remote_name))
                if text.strip().startswith("DONE"):
                    if not fut.done():
                        fut.set_result(True)
                return

            # data packet (hdr may be None): append to partial and parse HDR-framed chunks
            partial.extend(chunk)
            while True:
                if len(partial) < len(HDR_PREFIX):
                    break
                if not partial.startswith(HDR_PREFIX):
                    # find prefix later
                    idx = partial.find(HDR_PREFIX)
                    if idx == -1:
                        break
                    del partial[:idx]
                    continue
                # we have prefix - find newline
                if b"\n" not in partial:
                    break
                nl = partial.index(b"\n")
                header = bytes(partial[:nl]).decode(errors="ignore").strip()
                del partial[: nl + 1]
                parts = header.split()
                if len(parts) != 3 or parts[0] != "HDR":
                    # bad header -> fail
                    if not fut.done():
                        fut.set_exception(ValueError("Bad data header"))
                        return
                try:
                    crc_recv = int(parts[1])
                    length = int(parts[2])
                except Exception:
                    if not fut.done():
                        fut.set_exception(ValueError("Bad data header ints"))
                        return
                if len(partial) < length:
                    # wait for more bytes
                    # reinsert header? we already removed header; partial has payload waiting
                    # just break and wait
                    # reassemble when more data arrives
                    # but we must preserve crc/length across calls; we handle in the loop
                    # here, put header back? simpler: keep parsing only when enough bytes present
                    partial[:0]  # no-op, placeholder
                    # actually just break to wait for more bytes
                    # we kept crc_recv and length in locals for next while iteration when more bytes arrive
                    # but because we removed header, we must store expected; easiest is to re-add header to front
                    # Simpler approach: we will check length and if not enough, re-add the header bytes to front and break.
                    header_bytes = (HDR_PREFIX + f"{crc_recv} {length}\n".encode())
                    partial[:0] = header_bytes  # put back header
                    break
                # got full payload
                payload = bytes(partial[:length])
                del partial[:length]
                calc = zlib.crc32(payload) & 0xFFFFFFFF
                if calc != crc_recv:
                    # ignore corrupt chunk or raise — choose to raise so GUI knows
                    if not fut.done():
                        fut.set_exception(ValueError("CRC mismatch"))
                        return
                chunks.append(payload)
            return

        self._set_recv_cb(cb)
        # wait for DONE control (or exception)
        await fut
        data = b"".join(chunks)
        save_chunks(local_path, [(data, 0)])
        return len(data)
