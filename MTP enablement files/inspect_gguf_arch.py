import struct, os

path = r"C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf"
with open(path, 'rb') as f:
    f.read(4); f.read(4)
    tc = struct.unpack('<Q', f.read(8))[0]
    kc = struct.unpack('<Q', f.read(8))[0]
    def rv(f, t):
        if t==0: return struct.unpack('<B',f.read(1))[0]
        if t==1: return struct.unpack('<b',f.read(1))[0]
        if t==2: return struct.unpack('<H',f.read(2))[0]
        if t==3: return struct.unpack('<h',f.read(2))[0]
        if t==4: return struct.unpack('<I',f.read(4))[0]
        if t==5: return struct.unpack('<i',f.read(4))[0]
        if t==6: return struct.unpack('<f',f.read(4))[0]
        if t==7: return struct.unpack('<B',f.read(1))[0]!=0
        if t==8:
            n=struct.unpack('<Q',f.read(8))[0]; return f.read(n).decode('utf-8','replace')
        if t==9:
            et=struct.unpack('<I',f.read(4))[0]; n=struct.unpack('<Q',f.read(8))[0]
            return [rv(f,et) for _ in range(n)]
        if t==10: return struct.unpack('<Q',f.read(8))[0]
        if t==11: return struct.unpack('<q',f.read(8))[0]
        raise ValueError(t)
    for i in range(kc):
        kl=struct.unpack('<Q',f.read(8))[0]
        k=f.read(kl).decode('utf-8','replace')
        vt=struct.unpack('<I',f.read(4))[0]
        v=rv(f,vt)
        if k.startswith('tokenizer.ggml.tokens') or k=='tokenizer.chat_template':
            continue
        print(f"{k} = {v}")
