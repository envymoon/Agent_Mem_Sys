# L4  2026-11-26 20:14:27Z  (running)

- code `2789482 docs: VM-side kernel client`, runtime up 0.48 h (~1.1 CU)
- queue: ['pilot']  done: []  gave up: []
- now: line `pilot` attempt 1, run `l1_gptoss20b_mem0-local_sync_t20`, suite alive True, last write 0.1 min ago
- finished runs (6): kv_gptoss20b_ram0, kv_gptoss20b_ram8192, l1_gptoss20b_rag-pg_sync_t20, preflight, preflight_df5db7a1, rates_gptoss20b
- backup: {'mode': 'download+ack', 'ok': True, 'why': '0 acked', 'missing': ['kv_gptoss20b_ram0', 'kv_gptoss20b_ram8192', 'l1_gptoss20b_rag-pg_sync_t20', 'preflight', 'preflight_df5db7a1', 'rates_gptoss20b']}
- stop: None; 0.44 h since start, cap 5.0 h
- disk free 220.6 GB, RAM avail 46.0 GB, GPU NVIDIA L4, 94 %, 14284 MiB, 23034 MiB, 71.82 W

## problems

none

## supervisor events

    [2026-11-26 19:48:17Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 748
    [2026-11-26 20:04:27Z] setup attempt 1: rc=0 in 16.2 min
    [2026-11-26 20:04:27Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['pilot']
    [2026-11-26 20:04:28Z] start 'pilot' attempt 1/3 at 2789482 docs: VM-side kernel client

## suite.log (tail)

    L=  1024 rep1 recompute=333 gpu=17 ram=36(cache_n=1023) ssd_cold=42 ssd_warm=37 ms kv=36MB
    L=  1024 rep2 recompute=318 gpu=17 ram=29(cache_n=1023) ssd_cold=39 ssd_warm=38 ms kv=36MB
    L=  2048 rep0 recompute=606 gpu=18 ram=57(cache_n=2047) ssd_cold=54 ssd_warm=52 ms kv=60MB
    L=  2048 rep1 recompute=612 gpu=18 ram=55(cache_n=2047) ssd_cold=55 ssd_warm=50 ms kv=60MB
    L=  2048 rep2 recompute=609 gpu=17 ram=54(cache_n=2047) ssd_cold=53 ssd_warm=49 ms kv=60MB
    L=  4096 rep0 recompute=1223 gpu=19 ram=87(cache_n=4095) ssd_cold=83 ssd_warm=74 ms kv=108MB
    L=  4096 rep1 recompute=1214 gpu=19 ram=87(cache_n=4095) ssd_cold=84 ssd_warm=73 ms kv=108MB
    L=  4096 rep2 recompute=1211 gpu=19 ram=87(cache_n=4095) ssd_cold=91 ssd_warm=73 ms kv=108MB
    L=  8192 rep0 recompute=2496 gpu=22 ram=152(cache_n=8191) ssd_cold=142 ssd_warm=117 ms kv=204MB
    L=  8192 rep1 recompute=2501 gpu=22 ram=153(cache_n=8191) ssd_cold=137 ssd_warm=117 ms kv=204MB
    L=  8192 rep2 recompute=2497 gpu=22 ram=152(cache_n=8191) ssd_cold=153 ssd_warm=117 ms kv=204MB
    L= 12288 rep0 recompute=3866 gpu=25 ram=221(cache_n=12287) ssd_cold=210 ssd_warm=162 ms kv=300MB
    L= 12288 rep1 recompute=3899 gpu=25 ram=218(cache_n=12287) ssd_cold=198 ssd_warm=165 ms kv=300MB
    L= 12288 rep2 recompute=3945 gpu=30 ram=219(cache_n=12287) ssd_cold=196 ssd_warm=163 ms kv=300MB
    | L | recompute | gpu hit | RAM cache | SSD cold | SSD warm | save | KV MB |
    |---|---|---|---|---|---|---|---|
    | 1024 | 322 | 17 | 36 | 40 | 38 | 42 | 36 |
    | 2048 | 609 | 18 | 55 | 54 | 50 | 74 | 60 |
    | 4096 | 1214 | 19 | 87 | 84 | 73 | 134 | 108 |
    | 8192 | 2497 | 22 | 152 | 142 | 117 | 275 | 204 |
    | 12288 | 3899 | 25 | 219 | 198 | 163 | 413 | 300 |
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 1 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 0 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 8.142543077468872, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 122.9, "compute:CUDA_Host": 55.4}, "n_ctx_slot": 32768}
    proxy up
    [20:08:32] === kv_gptoss20b_ram0
    L=  1024 rep0 recompute=327 gpu=19 ram=341(cache_n=0) ssd_cold=43 ssd_warm=38 ms kv=33MB
    L=  1024 rep1 recompute=353 gpu=18 ram=349(cache_n=0) ssd_cold=40 ssd_warm=37 ms kv=33MB
    L=  1024 rep2 recompute=330 gpu=18 ram=340(cache_n=0) ssd_cold=41 ssd_warm=37 ms kv=33MB
    L=  2048 rep0 recompute=627 gpu=19 ram=651(cache_n=0) ssd_cold=54 ssd_warm=48 ms kv=57MB
    L=  2048 rep1 recompute=640 gpu=19 ram=649(cache_n=0) ssd_cold=55 ssd_warm=48 ms kv=57MB
    L=  2048 rep2 recompute=663 gpu=19 ram=656(cache_n=0) ssd_cold=55 ssd_warm=48 ms kv=57MB
    L=  4096 rep0 recompute=1264 gpu=20 ram=1277(cache_n=0) ssd_cold=80 ssd_warm=74 ms kv=105MB
    L=  4096 rep1 recompute=1273 gpu=21 ram=1293(cache_n=0) ssd_cold=87 ssd_warm=72 ms kv=105MB
    L=  4096 rep2 recompute=1268 gpu=20 ram=1272(cache_n=0) ssd_cold=82 ssd_warm=71 ms kv=105MB
    L=  8192 rep0 recompute=2577 gpu=23 ram=2564(cache_n=0) ssd_cold=134 ssd_warm=118 ms kv=201MB
    L=  8192 rep1 recompute=2540 gpu=24 ram=2565(cache_n=0) ssd_cold=143 ssd_warm=116 ms kv=201MB
    L=  8192 rep2 recompute=2559 gpu=23 ram=2586(cache_n=0) ssd_cold=150 ssd_warm=118 ms kv=201MB
    L= 12288 rep0 recompute=3935 gpu=27 ram=3941(cache_n=0) ssd_cold=211 ssd_warm=163 ms kv=297MB
    L= 12288 rep1 recompute=3952 gpu=26 ram=3968(cache_n=0) ssd_cold=188 ssd_warm=161 ms kv=297MB
    L= 12288 rep2 recompute=3925 gpu=27 ram=3952(cache_n=0) ssd_cold=194 ssd_warm=163 ms kv=297MB
    | L | recompute | gpu hit | RAM cache | SSD cold | SSD warm | save | KV MB |
    |---|---|---|---|---|---|---|---|
    | 1024 | 330 | 18 | 341 | 41 | 37 | 42 | 33 |
    | 2048 | 640 | 19 | 651 | 55 | 48 | 69 | 57 |
    | 4096 | 1268 | 20 | 1277 | 82 | 72 | 128 | 105 |
    | 8192 | 2559 | 23 | 2565 | 143 | 118 | 245 | 201 |
    | 12288 | 3935 | 27 | 3952 | 194 | 163 | 357 | 297 |
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 8.145601034164429, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [20:11:07] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.050026178359985, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [20:11:13] === l1_gptoss20b_rag-pg_sync_t20 (rag-pg) PROFILE=gptoss20b
    [20:12:06] done l1_gptoss20b_rag-pg_sync_t20: {"n_turns": 20, "n_qa": 10, "count": 20, "total_s": 34.97844913199992}
    [20:12:06] === l1_gptoss20b_mem0-local_sync_t20 (mem0-local) PROFILE=gptoss20b
