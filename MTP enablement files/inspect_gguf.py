import struct, os, sys

path = r"C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf"
print("exists:", os.path.exists(path))
print("size GB: %.2f" % (os.path.getsize(path)/1024**3))

with open(path, 'rb') as f:
    magic = f.read(4)
    assert magic == b'GGUF', magic
    version = struct.unpack('<I', f.read(4))[0]
    tensor_count = struct.unpack('<Q', f.read(8))[0]
    kv_count = struct.unpack('<Q', f.read(8))[0]
    print(f"version={version} tensor_count={tensor_count} kv_count={kv_count}")

    def read_value(f, t):
        if t == 0: return struct.unpack('<B', f.read(1))[0]
        if t == 1: return struct.unpack('<b', f.read(1))[0]
        if t == 2: return struct.unpack('<H', f.read(2))[0]
        if t == 3: return struct.unpack('<h', f.read(2))[0]
        if t == 4: return struct.unpack('<I', f.read(4))[0]
        if t == 5: return struct.unpack('<i', f.read(4))[0]
        if t == 6: return struct.unpack('<f', f.read(4))[0]
        if t == 7: return struct.unpack('<B', f.read(1))[0] != 0
        if t == 8:
            n = struct.unpack('<Q', f.read(8))[0]
            return f.read(n).decode('utf-8', errors='replace')
        if t == 9:
            et = struct.unpack('<I', f.read(4))[0]
            n = struct.unpack('<Q', f.read(8))[0]
            return [read_value(f, et) for _ in range(n)]
        if t == 10: return struct.unpack('<Q', f.read(8))[0]
        if t == 11: return struct.unpack('<q', f.read(8))[0]
        raise ValueError("unknown type %d" % t)

    for i in range(kv_count):
        klen = struct.unpack('<Q', f.read(8))[0]
        key = f.read(klen).decode('utf-8', errors='replace')
        vtype = struct.unpack('<I', f.read(4))[0]
        val = read_value(f, vtype)
        print(f"{key} = {val}")
