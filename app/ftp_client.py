import asyncio
import os
import zlib
from transport.transport import GBNTransport
from app.fileops import iter_chunks, save_chunks

SERVER_ADDR = ("127.0.0.1", 9000)


class FTPClient:
    def __init__(self, loss_rate=0.0):
        self.loss_rate = loss_rate
        self.connected = False
        self.transport = None

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

    # --------------------------------------
    async def send_command(self, line):
        self.transport.send(line.encode())

    async def recv_response(self):
        buf = bytearray()
        fut = asyncio.get_event_loop().create_future()

        def on_recv(chunk):
            buf.extend(chunk)
            if b"END\n" in buf:
                if not fut.done():
                    fut.set_result(bytes(buf))

        self.transport.set_callback(on_recv)
        resp = await fut
        self.transport.clear_callback()

        resp = resp.replace(b"END\n", b"")
        return resp.decode(errors="ignore")

    # --------------------------------------
    async def list_files(self):
        await self.send_command("LIST\n")
        resp = await self.recv_response()
        return [x for x in resp.split("\n") if x.strip()]

    async def delete_file(self, fname):
        await self.send_command(f"DELETE {fname}\n")
        resp = await self.recv_response()
        return "OK" in resp

    # --------------------------------------
    async def put_file(self, path, remote):
        size = os.path.getsize(path)
        print(f"[PUT] Uploading {path}, {size} bytes")

        await self.send_command(f"PUT {remote} {size}\n")
        resp = await self.recv_response()

        if not resp.startswith("OFFSET"):
            print("[PUT] Server:", resp)
            return

        offset = int(resp.split()[1])
        print("[PUT] Resume offset =", offset)

        sent = 0

        for off, data, crc in iter_chunks(path):
            if off < offset:
                sent = off + len(data)
                continue

            header = f"DATA {crc}\n".encode()
            self.transport.send(header + data)
            sent += len(data)

        self.transport.send(b"DONE\n")
        final = await self.recv_response()
        print("[PUT] Server:", final)

    # --------------------------------------
    async def get_file(self, remote, local):
        offset = os.path.getsize(local) if os.path.exists(local) else 0

        await self.send_command(f"GET {remote} {offset}\n")

        chunks = []
        fut = asyncio.get_event_loop().create_future()

        def on_recv(chunk):
            if chunk.startswith(b"DATA "):
                # must pull crc header
                try:
                    header_end = chunk.index(b"\n")
                    header = chunk[:header_end]
                    _, crc_str = header.decode().split()
                    crc = int(crc_str)
                    data = chunk[header_end + 1:]
                    chunks.append((data, crc))
                    return
                except:
                    return

            if b"DONE" in chunk:
                chunks.append((b"", 0))
                if not fut.done():
                    fut.set_result(True)

        self.transport.set_callback(on_recv)
        await fut
        self.transport.clear_callback()

        save_chunks(local, chunks)
        print(f"[GET] Saved {sum(len(c[0]) for c in chunks)} bytes to {local}")
