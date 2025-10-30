import zlib, os

CHUNK_SIZE = 16*1024

def iter_chunks(fpath):
    """Yield (data, crc) for each chunk of the file"""
    with open(fpath, "rb") as f:
        while True:
            data = f.read(CHUNK_SIZE)
            if not data:
                break
            yield data, zlib.crc32(data) & 0xffffffff

def save_chunks(fpath, chunks):
    """Save a list of chunks [(data, crc), ...] to file"""
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "wb") as f:
        for data, _ in chunks:
            f.write(data)
