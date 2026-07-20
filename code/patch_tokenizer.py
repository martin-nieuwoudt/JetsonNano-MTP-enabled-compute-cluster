with open('/home/jetson/llama.cpp/src/llama-model.cpp', 'r') as f:
    content = f.read()
old = '            } else if (\n                tokenizer_pre == "megrez") {\n                vocab.type_pre = LLAMA_VOCAB_PRE_TYPE_QWEN2;'
new = '            } else if (\n                tokenizer_pre == "deepseek-r1-qwen") {\n                vocab.type_pre = LLAMA_VOCAB_PRE_TYPE_QWEN2;\n            } else if (\n                tokenizer_pre == "megrez") {\n                vocab.type_pre = LLAMA_VOCAB_PRE_TYPE_QWEN2;'
if old in content:
    content = content.replace(old, new)
    with open('/home/jetson/llama.cpp/src/llama-model.cpp', 'w') as f:
        f.write(content)
    print('PATCHED')
else:
    print('NOT FOUND - checking for megrez...')
    if 'megrez' in content:
        print('megrez found but exact match failed')
    else:
        print('megrez not found either')