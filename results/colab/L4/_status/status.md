# L4  2026-11-26 07:44:10Z  (idle (queue empty))

- code `fc5e5c7 Colab L4 pilot: setup log after attempt 1`, runtime up 1.06 h (~2.5 CU)
- queue: ['pilot']  done: ['pilot']  gave up: []
- now: line `None` attempt 0, run `rates_gptoss20b`, suite alive False, last write 0.5 min ago
- finished runs (0): 
- backup: {'mode': 'download+ack', 'ok': True, 'why': '0 acked', 'missing': []}
- stop: None; 1.03 h since start, cap 5.0 h
- disk free 221.8 GB, RAM avail 50.3 GB, GPU NVIDIA L4, 0 %, 14258 MiB, 23034 MiB, 28.42 W

## problems

    [07:43:23] proxy failed
    [07:43:29] proxy failed
    [07:43:35] proxy failed
    [07:43:40] proxy failed

## supervisor events

    [2026-11-26 06:42:33Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h
    [2026-11-26 07:36:58Z] setup attempt 1: rc=143 in 54.4 min
    [2026-11-26 07:41:09Z] setup attempt 2: rc=0 in 2.1 min
    [2026-11-26 07:41:09Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['pilot']
    [2026-11-26 07:41:10Z] start 'pilot' attempt 1/3 at fc5e5c7 Colab L4 pilot: setup log after attempt 1
    [2026-11-26 07:44:10Z] finished 'pilot'
    [2026-11-26 07:44:10Z] queue empty at fc5e5c7 Colab L4 pilot: setup log after attempt 1; waiting up to 15 min for new lines in colab/queue.txt

## suite.log (tail)

    suggested: PROFILE=q4b (main).  q8b/llama8b OK; moe30b OK
    [07:42:36] === rates_gptoss20b depths 0,2048,4096,8192,12288,16384
      d=     0 pp   3604.9 tok/s
      d=     0 tg     83.0 tok/s
      d=  2048 pp   3535.1 tok/s
      d=  2048 tg     80.6 tok/s
      d=  4096 pp   3463.1 tok/s
      d=  4096 tg     79.1 tok/s
      d=  8192 pp   3207.9 tok/s
      d=  8192 tg     77.0 tok/s
      d= 12288 pp   3010.7 tok/s
      d= 12288 tg     74.8 tok/s
      d= 16384 pp   2835.1 tok/s
      d= 16384 tg     72.4 tok/s
    embedder (Qwen3-Embedding-0.6B-Q8_0.gguf) up
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.102263927459717, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy FAILED
    Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "/content/Agent_Mem_Sys/memprof/llm_proxy.py", line 31, in <module>
        from aiohttp import ClientSession, ClientTimeout, TCPConnector, web
    ModuleNotFoundError: No module named 'aiohttp'
    [07:43:23] proxy failed
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.078195571899414, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy FAILED
    Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "/content/Agent_Mem_Sys/memprof/llm_proxy.py", line 31, in <module>
        from aiohttp import ClientSession, ClientTimeout, TCPConnector, web
    ModuleNotFoundError: No module named 'aiohttp'
    [07:43:29] proxy failed
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.091311454772949, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy FAILED
    Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "/content/Agent_Mem_Sys/memprof/llm_proxy.py", line 31, in <module>
        from aiohttp import ClientSession, ClientTimeout, TCPConnector, web
    ModuleNotFoundError: No module named 'aiohttp'
    [07:43:35] proxy failed
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.066547870635986, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy FAILED
    Traceback (most recent call last):
      File "<frozen runpy>", line 198, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File "/content/Agent_Mem_Sys/memprof/llm_proxy.py", line 31, in <module>
        from aiohttp import ClientSession, ClientTimeout, TCPConnector, web
    ModuleNotFoundError: No module named 'aiohttp'
    [07:43:40] proxy failed
    [07:43:40] suite done -> /content/results/L4
