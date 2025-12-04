import asyncio
import os
import zlib

from transport.transport import GBNTransport
from app.fileops import iter_chunks, save_chunks

SERVER_DIR = "./server_files"
os.makedirs(SERVER_DIR, exist_ok=True)

clients_state = {}   # transport → {"fname": str, "chunks": []}


async def handle_command(transport, data):
    # -----------------------------------------
    # DATA packet from client during PUT upload
    # -----------------------------------------
    if data.startswith(b"DATA "):
        try:
            header_end = data.index(b"\n")
            header = data[:header_end].decode()
            _, crc_str = header.split()
            crc_recv = int(crc_str)
            chunk = data[header_end + 1:]
        except:
            transport.send(b"ERROR bad DATA\nEND\n")
            return

        if transport not in clients_state:
            transport.send(b"ERROR no PUT\nEND\n")
            return

        # verify CRC
        if (zlib.crc32(chunk) & 0xFFFFFFFF) != crc_recv:
            transport.send(b"CRCERR\nEND\n")
            return

        clients_state[transport]["chunks"].append((chunk, crc_recv))
        return

    # -----------------------------------------
    # Decode command (plain-text)
    # -----------------------------------------
    try:
        cmd = data.decode(errors="ignore").strip()
    except:
        transport.send(b"ERROR decode\nEND\n")
        return

    parts = cmd.split()
    if not parts:
        transport.send(b"ERROR empty\nEND\n")
        return

    # -----------------------------------------
    # LIST
    # -----------------------------------------
    if parts[0] == "LIST":
        files = os.listdir(SERVER_DIR)
        resp = "\n".join(files).encode() + b"\nEND\n"
        transport.send(resp)
        return

    # -----------------------------------------
    # DELETE <fname>
    # -----------------------------------------
    if parts[0] == "DELETE" and len(parts) == 2:
        fname = os.path.join(SERVER_DIR, parts[1])
        if os.path.exists(fname):
            os.remove(fname)
            transport.send(b"OK\nEND\n")
        else:
            transport.send(b"NOTFOUND\nEND\n")
        return

    # -----------------------------------------
    # PUT <fname> <size>
    # -----------------------------------------
    if parts[0] == "PUT" and len(parts) == 3:
        fname = parts[1]
        full_path = os.path.join(SERVER_DIR, fname)

        offset = os.path.getsize(full_path) if os.path.exists(full_path) else 0

        clients_state[transport] = {
            "fname": full_path,
            "chunks": []
        }

        msg = f"OFFSET {offset}\nEND\n".encode()
        transport.send(msg)
        return

    # -----------------------------------------
    # DONE — end of a PUT upload
    # -----------------------------------------
    if parts[0] == "DONE":
        if transport not in clients_state:
            transport.send(b"ERROR no PUT\nEND\n")
            return

        st = clients_state.pop(transport)
        save_chunks(st["fname"], st["chunks"])

        transport.send(b"OK\nEND\n")
        return

    # -----------------------------------------
    # GET <fname> <offset>
    # -----------------------------------------
    if parts[0] == "GET" and len(parts) == 3:
        fname = parts[1]
        offset = int(parts[2])

        full_path = os.path.join(SERVER_DIR, fname)
        if not os.path.exists(full_path):
            transport.send(b"NOTFOUND\nEND\n")
            return

        for off, data, crc in iter_chunks(full_path, start_offset=offset):
            header = f"DATA {crc}\n".encode()
            transport.send(header + data)

        transport.send(b"DONE\nEND\n")
        return

    # unknown
    transport.send(b"ERROR unknown\nEND\n")
