import asyncio, os, zlib, time
from transport.transport import GBNTransport
from app.fileops import iter_chunks, save_chunks
from tools.metrics import Metrics

SERVER_DIR = "./server_files"
os.makedirs(SERVER_DIR, exist_ok=True)

metrics = Metrics()
clients_state = {}

async def handle_command(client, data):
    cmd = data.decode().strip()
    print("[Server] Command:", cmd)

    if cmd == "LIST":
        files = os.listdir(SERVER_DIR)
        client.send(("\n".join(files)+"\n").encode())

    elif cmd.startswith("GET "):
        fname = cmd[4:].strip()
        fpath = os.path.join(SERVER_DIR, fname)
        if not os.path.exists(fpath):
            client.send(b"ERROR: file not found\n")
            return
        start_time = time.time()
        for chunk, crc in iter_chunks(fpath):
            client.send(chunk)
            metrics.record_bytes(len(chunk))
        metrics.record_delay((time.time()-start_time)*1000)

    elif cmd.startswith("PUT "):
        fname = cmd[4:].strip()
        fpath = os.path.join(SERVER_DIR, fname)
        clients_state[client] = {"fpath": fpath, "chunks": []}
        client.send(b"READY\n")

    elif cmd.startswith("DATA "):
        if client not in clients_state:
            client.send(b"ERROR: unexpected data\n")
            return
        payload = data[5:]
        clients_state[client]["chunks"].append((payload, zlib.crc32(payload) & 0xffffffff))
        metrics.record_bytes(len(payload))

    elif cmd == "END":
        if client not in clients_state:
            return
        save_chunks(clients_state[client]["fpath"], clients_state[client]["chunks"])
        client.send(b"OK\n")
        del clients_state[client]

    else:
        client.send(b"Unknown command\n")

async def main():
    t = GBNTransport(local_port=9000)
    t.on_receive_cb = lambda data: asyncio.create_task(handle_command(t, data))
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(lambda: t, local_addr=('0.0.0.0', 9000))
    print("[Server] Running...")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
