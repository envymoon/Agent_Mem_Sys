# L4  2026-11-27 09:42:24Z  (running)

- code `a1b06c4 Colab status: first lme attempt stopped (embedder context), relaunching`, runtime up 2.89 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme']  done: ['pilot', 'l1', 'score budget # after l1']  gave up: []
- now: line `lme` attempt 1, run `lme_gptoss20b_mem0-local_i233_t0`, suite alive True, last write 0.0 min ago
- finished runs (20): l1_gptoss20b_graphiti_sync_t100, l1_gptoss20b_graphiti_sync_t20, l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-local_sync_t20, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_mem0-pg_sync_t20, l1_gptoss20b_mem0-qdrant_sync_t100, l1_gptoss20b_mem0-qdrant_sync_t20, l1_gptoss20b_rag-pg_sync_t100, l1_gptoss20b_rag-pg_sync_t20, lme_gptoss20b_graphiti_i0_t60, lme_gptoss20b_mem0-local_i0_t60, lme_gptoss20b_mem0-local_i70_t0, lme_gptoss20b_mem0-pg_i0_t60, lme_gptoss20b_mem0-pg_i70_t0, lme_gptoss20b_mem0-qdrant_i0_t60, lme_gptoss20b_mem0-qdrant_i70_t0, lme_gptoss20b_rag-pg_i0_t60, lme_gptoss20b_rag-pg_i233_t0, lme_gptoss20b_rag-pg_i70_t0
- backup: {'mode': 'download+ack', 'ok': True, 'why': '27 acked', 'missing': ['lme_gptoss20b_mem0-pg_i70_t0', 'lme_gptoss20b_mem0-qdrant_i70_t0', 'lme_gptoss20b_rag-pg_i233_t0']}
- stop: None; 2.84 h since start, cap 5.0 h
- disk free 220.3 GB, RAM avail 38.2 GB, GPU NVIDIA L4, 89 %, 16092 MiB, 23034 MiB, 70.11 W

## problems

none

## supervisor events

    [2026-11-27 06:52:23Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 832
    [2026-11-27 07:09:41Z] setup attempt 1: rc=0 in 17.3 min
    [2026-11-27 07:09:41Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['l1', 'score budget # after l1', 'lme', 'score budget # after lme']
    [2026-11-27 07:09:42Z] start 'l1' attempt 1/3 at a1b06c4 Colab status: first lme attempt stopped (embedder context), relaunching
    [2026-11-27 07:10:12Z] finished 'l1'
    [2026-11-27 07:10:12Z] start 'score budget # after l1' attempt 1/3 at a1b06c4 Colab status: first lme attempt stopped (embedder context), relaunching
    [2026-11-27 07:10:43Z] finished 'score budget # after l1'
    [2026-11-27 07:10:43Z] start 'lme' attempt 1/3 at a1b06c4 Colab status: first lme attempt stopped (embedder context), relaunching

## suite.log (tail)

    embedder (Qwen3-Embedding-0.6B-Q8_0.gguf) up
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.455079793930054, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [07:09:51] skip l1_gptoss20b_rag-pg_sync_t100
    [07:09:51] skip l1_gptoss20b_mem0-local_sync_t100
    [07:09:51] skip l1_gptoss20b_mem0-pg_sync_t100
    [07:09:51] skip l1_gptoss20b_mem0-qdrant_sync_t100
    [07:09:51] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.021084785461426, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [07:10:19] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.029597520828247, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [07:10:49] === lme_gptoss20b_rag-pg_i70_t0 (rag-pg) PROFILE=gptoss20b
    [07:26:04] done lme_gptoss20b_rag-pg_i70_t0: {"n_turns": 242, "n_qa": 1, "count": 242, "total_s": 891.4744672019999}
    [07:26:04] === lme_gptoss20b_mem0-local_i70_t0 (mem0-local) PROFILE=gptoss20b
    [08:06:21] done lme_gptoss20b_mem0-local_i70_t0: {"n_turns": 242, "n_qa": 1, "count": 809, "total_s": 2382.7901677570003}
    [08:06:21] === lme_gptoss20b_mem0-pg_i70_t0 (mem0-pg) PROFILE=gptoss20b
    [08:43:57] done lme_gptoss20b_mem0-pg_i70_t0: {"n_turns": 242, "n_qa": 1, "count": 845, "total_s": 2221.0874503230007}
    [08:43:57] === lme_gptoss20b_mem0-qdrant_i70_t0 (mem0-qdrant) PROFILE=gptoss20b
    [09:21:20] done lme_gptoss20b_mem0-qdrant_i70_t0: {"n_turns": 242, "n_qa": 1, "count": 786, "total_s": 2209.0849712930003}
    [09:21:20] === lme_gptoss20b_rag-pg_i233_t0 (rag-pg) PROFILE=gptoss20b
    [09:38:18] done lme_gptoss20b_rag-pg_i233_t0: {"n_turns": 240, "n_qa": 1, "count": 240, "total_s": 984.3047961660013}
    [09:38:18] === lme_gptoss20b_mem0-local_i233_t0 (mem0-local) PROFILE=gptoss20b
