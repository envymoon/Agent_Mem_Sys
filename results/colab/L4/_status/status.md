# L4  2026-11-27 13:41:21Z  (running)

- code `146baac Colab layer 1: lme item 233 progress`, runtime up 1.48 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme']  done: ['pilot', 'l1', 'score budget # after l1']  gave up: []
- now: line `lme` attempt 1, run `lme_gptoss20b_mem0-pg_i366_t0`, suite alive True, last write 0.0 min ago
- finished runs (25): l1_gptoss20b_graphiti_sync_t100, l1_gptoss20b_graphiti_sync_t20, l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-local_sync_t20, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_mem0-pg_sync_t20, l1_gptoss20b_mem0-qdrant_sync_t100, l1_gptoss20b_mem0-qdrant_sync_t20, l1_gptoss20b_rag-pg_sync_t100, l1_gptoss20b_rag-pg_sync_t20, lme_gptoss20b_graphiti_i0_t60, lme_gptoss20b_mem0-local_i0_t60, lme_gptoss20b_mem0-local_i233_t0, lme_gptoss20b_mem0-local_i366_t0, lme_gptoss20b_mem0-local_i70_t0, lme_gptoss20b_mem0-pg_i0_t60, lme_gptoss20b_mem0-pg_i233_t0, lme_gptoss20b_mem0-pg_i70_t0, lme_gptoss20b_mem0-qdrant_i0_t60, lme_gptoss20b_mem0-qdrant_i233_t0, lme_gptoss20b_mem0-qdrant_i70_t0, lme_gptoss20b_rag-pg_i0_t60, lme_gptoss20b_rag-pg_i233_t0, lme_gptoss20b_rag-pg_i366_t0, lme_gptoss20b_rag-pg_i70_t0
- backup: {'mode': 'download+ack', 'ok': True, 'why': '41 acked', 'missing': ['lme_gptoss20b_mem0-local_i366_t0', 'lme_gptoss20b_rag-pg_i366_t0']}
- stop: None; 1.44 h since start, cap 5.0 h
- disk free 220.2 GB, RAM avail 38.6 GB, GPU NVIDIA L4, 0 %, 16094 MiB, 23034 MiB, 58.91 W

## problems

none

## supervisor events

    [2026-11-27 12:15:24Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 711
    [2026-11-27 12:31:20Z] setup attempt 1: rc=0 in 15.8 min
    [2026-11-27 12:31:20Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['l1', 'score budget # after l1', 'lme', 'score budget # after lme']
    [2026-11-27 12:31:20Z] start 'l1' attempt 1/3 at 146baac Colab layer 1: lme item 233 progress
    [2026-11-27 12:31:50Z] finished 'l1'
    [2026-11-27 12:31:50Z] start 'score budget # after l1' attempt 1/3 at 146baac Colab layer 1: lme item 233 progress
    [2026-11-27 12:32:20Z] finished 'score budget # after l1'
    [2026-11-27 12:32:21Z] start 'lme' attempt 1/3 at 146baac Colab layer 1: lme item 233 progress

## suite.log (tail)

    embedder (Qwen3-Embedding-0.6B-Q8_0.gguf) up
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.4379777908325195, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [12:31:29] skip l1_gptoss20b_rag-pg_sync_t100
    [12:31:29] skip l1_gptoss20b_mem0-local_sync_t100
    [12:31:29] skip l1_gptoss20b_mem0-pg_sync_t100
    [12:31:29] skip l1_gptoss20b_mem0-qdrant_sync_t100
    [12:31:29] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.0242955684661865, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    lme_gptoss20b_mem0-local_i233_t0: n=1 F1=0.148 J=0.000
    lme_gptoss20b_mem0-local_i70_t0: n=1 F1=0.000 J=0.000
    lme_gptoss20b_mem0-pg_i233_t0: n=1 F1=0.038 J=0.000
    lme_gptoss20b_mem0-pg_i70_t0: n=1 F1=0.000 J=0.000
    lme_gptoss20b_mem0-qdrant_i233_t0: n=1 F1=0.043 J=0.000
    lme_gptoss20b_mem0-qdrant_i70_t0: n=1 F1=0.000 J=0.000
    lme_gptoss20b_rag-pg_i233_t0: n=1 F1=0.037 J=0.000
    lme_gptoss20b_rag-pg_i70_t0: n=1 F1=0.054 J=1.000
    [12:32:02] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.034006595611572, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [12:32:27] skip lme_gptoss20b_rag-pg_i70_t0
    [12:32:27] skip lme_gptoss20b_mem0-local_i70_t0
    [12:32:27] skip lme_gptoss20b_mem0-pg_i70_t0
    [12:32:27] skip lme_gptoss20b_mem0-qdrant_i70_t0
    [12:32:27] skip lme_gptoss20b_rag-pg_i233_t0
    [12:32:27] skip lme_gptoss20b_mem0-local_i233_t0
    [12:32:27] skip lme_gptoss20b_mem0-pg_i233_t0
    [12:32:27] skip lme_gptoss20b_mem0-qdrant_i233_t0
    [12:32:27] === lme_gptoss20b_rag-pg_i366_t0 (rag-pg) PROFILE=gptoss20b
    [12:49:36] done lme_gptoss20b_rag-pg_i366_t0: {"n_turns": 205, "n_qa": 1, "count": 205, "total_s": 1005.778542964}
    [12:49:36] === lme_gptoss20b_mem0-local_i366_t0 (mem0-local) PROFILE=gptoss20b
    [13:27:34] done lme_gptoss20b_mem0-local_i366_t0: {"n_turns": 205, "n_qa": 1, "count": 767, "total_s": 2244.217672335}
    [13:27:34] === lme_gptoss20b_mem0-pg_i366_t0 (mem0-pg) PROFILE=gptoss20b
