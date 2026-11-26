# L4  2026-11-26 21:44:28Z  (idle (queue empty))

- code `5dcc6fe colab patrol: L4 pilot, LoCoMo l1 done for 5 systems, LME in progress`, runtime up 1.98 h (~4.6 CU)
- queue: ['pilot']  done: ['pilot']  gave up: []
- now: line `None` attempt 0, run `None`, suite alive False, last write 7.2 min ago
- finished runs (15): kv_gptoss20b_ram0, kv_gptoss20b_ram8192, l1_gptoss20b_graphiti_sync_t20, l1_gptoss20b_mem0-local_sync_t20, l1_gptoss20b_mem0-pg_sync_t20, l1_gptoss20b_mem0-qdrant_sync_t20, l1_gptoss20b_rag-pg_sync_t20, lme_gptoss20b_graphiti_i0_t60, lme_gptoss20b_mem0-local_i0_t60, lme_gptoss20b_mem0-pg_i0_t60, lme_gptoss20b_mem0-qdrant_i0_t60, lme_gptoss20b_rag-pg_i0_t60, preflight, preflight_df5db7a1, rates_gptoss20b
- backup: {'mode': 'download+ack', 'ok': True, 'why': '12 acked', 'missing': ['lme_gptoss20b_graphiti_i0_t60', 'lme_gptoss20b_mem0-pg_i0_t60', 'lme_gptoss20b_mem0-qdrant_i0_t60']}
- stop: None; 1.94 h since start, cap 5.0 h
- disk free 220.5 GB, RAM avail 46.8 GB, GPU NVIDIA L4, 0 %, 14286 MiB, 23034 MiB, 30.50 W

## problems

none

## supervisor events

    [2026-11-26 19:48:17Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 748
    [2026-11-26 20:04:27Z] setup attempt 1: rc=0 in 16.2 min
    [2026-11-26 20:04:27Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['pilot']
    [2026-11-26 20:04:28Z] start 'pilot' attempt 1/3 at 2789482 docs: VM-side kernel client
    [2026-11-26 21:37:28Z] finished 'pilot'
    [2026-11-26 21:37:30Z] queue empty at 5dcc6fe colab patrol: L4 pilot, LoCoMo l1 done for 5 systems, LME in progress; waiting up to 15 min for new lines in colab/queue.txt

## suite.log (tail)

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
    [20:14:45] done l1_gptoss20b_mem0-local_sync_t20: {"n_turns": 20, "n_qa": 10, "count": 34, "total_s": 129.11672842000007}
    [20:14:45] === l1_gptoss20b_mem0-pg_sync_t20 (mem0-pg) PROFILE=gptoss20b
    [20:17:09] done l1_gptoss20b_mem0-pg_sync_t20: {"n_turns": 20, "n_qa": 10, "count": 32, "total_s": 114.64504772300006}
    [20:17:09] === l1_gptoss20b_mem0-qdrant_sync_t20 (mem0-qdrant) PROFILE=gptoss20b
    [20:19:39] done l1_gptoss20b_mem0-qdrant_sync_t20: {"n_turns": 20, "n_qa": 10, "count": 39, "total_s": 120.08932625900002}
    [20:19:39] === l1_gptoss20b_graphiti_sync_t20 (graphiti) PROFILE=gptoss20b
    [20:25:26] done l1_gptoss20b_graphiti_sync_t20: {"n_turns": 20, "n_qa": 10, "count": 26, "total_s": 317.0623321859998}
    [20:25:26] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 8.148076295852661, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [20:25:36] === lme_gptoss20b_rag-pg_i0_t60 (rag-pg) PROFILE=gptoss20b
    [20:29:30] done lme_gptoss20b_rag-pg_i0_t60: {"n_turns": 64, "n_qa": 1, "count": 64, "total_s": 204.88938056999996}
    [20:29:30] === lme_gptoss20b_mem0-local_i0_t60 (mem0-local) PROFILE=gptoss20b
    [20:40:00] done lme_gptoss20b_mem0-local_i0_t60: {"n_turns": 64, "n_qa": 1, "count": 236, "total_s": 596.421117293}
    [20:40:00] === lme_gptoss20b_mem0-pg_i0_t60 (mem0-pg) PROFILE=gptoss20b
    [20:49:20] done lme_gptoss20b_mem0-pg_i0_t60: {"n_turns": 64, "n_qa": 1, "count": 204, "total_s": 526.9003688950002}
    [20:49:20] === lme_gptoss20b_mem0-qdrant_i0_t60 (mem0-qdrant) PROFILE=gptoss20b
    [20:58:54] done lme_gptoss20b_mem0-qdrant_i0_t60: {"n_turns": 64, "n_qa": 1, "count": 188, "total_s": 540.1381046329998}
    [20:58:54] === lme_gptoss20b_graphiti_i0_t60 (graphiti) PROFILE=gptoss20b
    [21:36:29] done lme_gptoss20b_graphiti_i0_t60: {"n_turns": 64, "n_qa": 1, "count": 231, "total_s": 2221.8605088620006}
    [21:36:29] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 7.942105770111084, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    l1_gptoss20b_graphiti_sync_t20: n=10 F1=0.046 J=0.100
    l1_gptoss20b_mem0-local_sync_t20: n=10 F1=0.119 J=0.600
    l1_gptoss20b_mem0-pg_sync_t20: n=10 F1=0.113 J=0.600
    l1_gptoss20b_mem0-qdrant_sync_t20: n=10 F1=0.134 J=0.600
    l1_gptoss20b_rag-pg_sync_t20: n=10 F1=0.163 J=0.800
    lme_gptoss20b_graphiti_i0_t60: n=1 F1=0.444 J=1.000
    lme_gptoss20b_mem0-local_i0_t60: n=1 F1=0.444 J=1.000
    lme_gptoss20b_mem0-pg_i0_t60: n=1 F1=0.444 J=1.000
    lme_gptoss20b_mem0-qdrant_i0_t60: n=1 F1=0.444 J=1.000
    lme_gptoss20b_rag-pg_i0_t60: n=1 F1=0.000 J=0.000
    [21:37:17] suite done -> /content/results/L4
    [21:37:17] suite done -> /content/results/L4
