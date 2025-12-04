import zlib
import os

CHUNK_SIZE = 16 * 1024

def iter_chunks(fpath, start_offset=0):
    """Generate (offset, data, crc) binary chunks."""
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
    """Write [(data, crc), ...] binary chunks to file."""
    os.makedirs(os.path.dirname(fpath), exist_ok=True)

    # append mode for resumable downloads
    mode = "ab" if os.path.exists(fpath) else "wb"

    with open(fpath, mode) as f:
        for data, _crc in chunks:
            f.write(data)
