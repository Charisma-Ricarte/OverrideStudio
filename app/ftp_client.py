import asyncio, zlib, os, time
from transport.transport import GBNTransport
from transport.lossy_shim import LossySocket
from tools.metrics import Metrics

CHUNK_SIZE = 16*1024

class FTPClient:
    def __init__(self, server_addr=('127.0.0.1',9000), loss_rate=0.05):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.lossy = LossySocket(sock, loss_rate)
        self.t = GBNTransport(local_port=0, remote_addr=server_addr, loss_wrapper=self.lossy)
        self.t.on_receive_cb = self.on_receive
        self.loop = asyncio.get_event_loop()
        self.recv_data = bytearray()
        self.metrics = Metrics()
        self.put_state = None
        self.get_state = None

    async def start(self):
        await self.loop.create_datagram_endpoint(lambda: self.t, local_addr=('0.0.0.0',0))

    def send_command(self, cmd: str):
        self.t.send(cmd.encode())

    def on_receive(self, data):
        self.recv_data.extend(data)
        print("[Client] Received:", data.decode())

    async def put_file(self, local_path, remote_name, resume=False):
        offset = 0
        if resume and os.path.exists(local_path + ".resume"):
            offset = int(open(local_path + ".resume").read())
        self.send_command(f"PUT {remote_name}\n")
        await asyncio.sleep(0.5)
        with open(local_path, "rb") as f:
            f.seek(offset)
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                self.send_command(b"DATA " + chunk)
                self.metrics.record_bytes(len(chunk))
                offset += len(chunk)
                if resume:
                    with open(local_path + ".resume", "w") as rf:
                        rf.write(str(offset))
        self.send_command("END")
        if os.path.exists(local_path + ".resume"):
            os.remove(local_path + ".resume")
        print("[Client] PUT complete")

    async def get_file(self, remote_name, local_path, resume=False):
        offset = 0
        if resume and os.path.exists(local_path):
            offset = os.path.getsize(local_path)
        start_time = time.time()
        self.send_command(f"GET {remote_name}\n")
        await asyncio.sleep(2)
        mode = "r+b" if os.path.exists(local_path) else "wb"
        with open(local_path, mode) as f:
            f.seek(offset)
            f.write(self.recv_data)
        self.metrics.record_delay((time.time()-start_time)*1000)
        print(f"[Client] GET complete, {len(self.recv_data)} bytes")

async def main():
    client = FTPClient()
    await client.start()
    await client.get_file("example.txt", "downloaded_example.txt", resume=True)
    await client.put_file("upload_me.txt", "uploaded_example.txt", resume=True)
    print(client.metrics.report())

if __name__ == "__main__":
    asyncio.run(main())
