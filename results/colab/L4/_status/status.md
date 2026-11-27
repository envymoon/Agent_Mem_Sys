# L4  2026-11-27 04:25:39Z  (running)

- code `821542b Colab status: layer-1 runtime building llama.cpp`, runtime up 0.89 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme']  done: []  gave up: []
- now: line `l1` attempt 1, run `l1_gptoss20b_mem0-qdrant_sync_t100`, suite alive True, last write 0.0 min ago
- finished runs (3): l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_rag-pg_sync_t100
- backup: {'mode': 'download+ack', 'ok': True, 'why': '15 acked', 'missing': ['l1_gptoss20b_mem0-local_sync_t100', 'l1_gptoss20b_mem0-pg_sync_t100', 'l1_gptoss20b_rag-pg_sync_t100']}
- stop: None; 0.84 h since start, cap 5.0 h
- disk free 220.5 GB, RAM avail 39.1 GB, GPU NVIDIA L4, 92 %, 14284 MiB, 23034 MiB, 71.27 W

## problems

none

## supervisor events

    [2026-11-27 03:35:39Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 780
    [2026-11-27 03:53:02Z] setup attempt 1: rc=0 in 17.4 min
    [2026-11-27 03:53:02Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['l1', 'score budget # after l1', 'lme', 'score budget # after lme']
    [2026-11-27 03:53:03Z] start 'l1' attempt 1/3 at 821542b Colab status: layer-1 runtime building llama.cpp

## suite.log (tail)

    embedder (Qwen3-Embedding-0.6B-Q8_0.gguf) up
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.5347044467926025, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [03:53:12] === l1_gptoss20b_rag-pg_sync_t100 (rag-pg) PROFILE=gptoss20b
    [03:56:43] done l1_gptoss20b_rag-pg_sync_t100: {"n_turns": 100, "n_qa": 47, "count": 100, "total_s": 191.31127433899997}
    [03:56:43] === l1_gptoss20b_mem0-local_sync_t100 (mem0-local) PROFILE=gptoss20b
    [04:07:56] done l1_gptoss20b_mem0-local_sync_t100: {"n_turns": 100, "n_qa": 47, "count": 161, "total_s": 642.5273290540001}
    [04:07:56] === l1_gptoss20b_mem0-pg_sync_t100 (mem0-pg) PROFILE=gptoss20b
    [04:18:42] done l1_gptoss20b_mem0-pg_sync_t100: {"n_turns": 100, "n_qa": 47, "count": 157, "total_s": 615.1927671079998}
    [04:18:42] === l1_gptoss20b_mem0-qdrant_sync_t100 (mem0-qdrant) PROFILE=gptoss20b
