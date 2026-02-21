import urllib.request, json, os, time

# OpenVINO GenAI
try:
    import openvino_genai as ov_genai
    print('openvino_genai version:', ov_genai.__version__)
except Exception as e:
    print('openvino_genai error:', e)

# Sentence-transformers model
st_path = 'C:/hfoDev/.hfo_models/models--sentence-transformers--all-MiniLM-L6-v2'
if os.path.exists(st_path):
    for root, dirs, files in os.walk(st_path):
        for f in files:
            if f.endswith('.bin') or f.endswith('.onnx') or f.endswith('.xml'):
                full = os.path.join(root, f)
                print(f'  ST: {f} {os.path.getsize(full)//1024**2}MB')

# OpenVINO properties
try:
    import openvino as ov
    core = ov.Core()
    try:
        mem = core.get_property('GPU', 'DEVICE_TOTAL_MEM_SIZE')
        print(f'GPU TOTAL MEM: {mem // 1024**2} MB')
    except Exception as e:
        print('GPU mem prop:', e)
    try:
        print('NPU compute:', core.get_property('NPU', 'OPTIMIZATION_CAPABILITIES'))
    except Exception as e:
        print('NPU caps:', e)
except Exception as e:
    print('OV error:', e)

# Ollama quick inference speed test
print('\nOllama GPU inference test...')
payload = {
    'model': 'qwen2.5:3b',
    'prompt': 'Hello',
    'stream': False,
    'options': {'num_gpu': -1},
    'keep_alive': '1m'
}
body = json.dumps(payload).encode()
req = urllib.request.Request(
    'http://127.0.0.1:11434/api/generate',
    data=body,
    headers={'Content-Type': 'application/json'}
)
try:
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    elapsed = time.time() - t0
    eval_count = d.get('eval_count', 0)
    eval_dur = d.get('eval_duration', 1) / 1e9
    tps = eval_count / eval_dur if eval_dur > 0 else 0
    print(f'  eval_count={eval_count}, elapsed={elapsed:.1f}s, tokens/sec={tps:.1f}')
    print(f'  response: {d.get("response","")[:60]}')
except Exception as e:
    print(f'  Ollama test error: {e}')
