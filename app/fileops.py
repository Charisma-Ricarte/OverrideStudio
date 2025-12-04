# app/fileops.py
import zlib
import os

CHUNK_SIZE = 16 * 1024

def iter_chunks(fpath, start_offset=0):
    """
    Yield (offset, data, crc) for each chunk starting at start_offset.
    """
    with open(fpath, "rb") as f:
        f.seek(start_offset)
        offset = start_offset
        while True:
            data = f.read(CHUNK_SIZE)
            if not data:
                break
            crc = zlib.crc32(data) & 0xFFFFFFFF
            yield offset, data, crc
            offset += len(data)

def save_chunks(fpath, chunks):
    """
    Write list of (data, crc) to fpath (overwrite).
    """
    dname = os.path.dirname(fpath)
    if dname:
        os.makedirs(dname, exist_ok=True)
    with open(fpath, "wb") as f:
        for data, _ in chunks:
            f.write(data)

def count_chunks(fpath):
    size = os.path.getsize(fpath)
    if size == 0:
        return 1
    return (size + CHUNK_SIZE - 1) // CHUNK_SIZE
