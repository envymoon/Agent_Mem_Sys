# L4  2026-11-28 01:33:02Z  (idle (queue empty))

- code `4da3040 Colab: async lme i366 progress (runtime 2)`, runtime up 4.3 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme', 'kprof # retry', 'l1 # async retry', 'score budget # after async l1 retry', 'lme # async retry', 'score budget # after async lme retry']  done: ['pilot', 'l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'kprof # retry', 'l1 # async retry', 'score budget # after async l1 retry', 'lme # async retry', 'score budget # after async lme retry']  gave up: ['kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme']
- now: line `None` attempt 0, run `None`, suite alive False, last write 1.6 min ago
- finished runs (47): kprof_gptoss20b_mem0-local_async_think5, kprof_gptoss20b_mem0-pg_async_think5, kprof_gptoss20b_mem0-qdrant_async_think5, kprof_gptoss20b_rag-pg_async_think5, l1_gptoss20b_graphiti_sync_t100, l1_gptoss20b_graphiti_sync_t20, l1_gptoss20b_mem0-local_async_think5_t100, l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-local_sync_t20, l1_gptoss20b_mem0-pg_async_think5_t100, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_mem0-pg_sync_t20, l1_gptoss20b_mem0-qdrant_async_think5_t100, l1_gptoss20b_mem0-qdrant_sync_t100, l1_gptoss20b_mem0-qdrant_sync_t20, l1_gptoss20b_rag-pg_async_think5_t100, l1_gptoss20b_rag-pg_sync_t100, l1_gptoss20b_rag-pg_sync_t20, lme_gptoss20b_graphiti_i0_t60, lme_gptoss20b_mem0-local_i0_t60, lme_gptoss20b_mem0-local_i233_t0, lme_gptoss20b_mem0-local_i233_t0_async_think5, lme_gptoss20b_mem0-local_i366_t0, lme_gptoss20b_mem0-local_i366_t0_async_think5, lme_gptoss20b_mem0-local_i70_t0, lme_gptoss20b_mem0-local_i70_t0_async_think5, lme_gptoss20b_mem0-pg_i0_t60, lme_gptoss20b_mem0-pg_i233_t0, lme_gptoss20b_mem0-pg_i233_t0_async_think5, lme_gptoss20b_mem0-pg_i366_t0, lme_gptoss20b_mem0-pg_i366_t0_async_think5, lme_gptoss20b_mem0-pg_i70_t0, lme_gptoss20b_mem0-pg_i70_t0_async_think5, lme_gptoss20b_mem0-qdrant_i0_t60, lme_gptoss20b_mem0-qdrant_i233_t0, lme_gptoss20b_mem0-qdrant_i233_t0_async_think5, lme_gptoss20b_mem0-qdrant_i366_t0, lme_gptoss20b_mem0-qdrant_i366_t0_async_think5, lme_gptoss20b_mem0-qdrant_i70_t0, lme_gptoss20b_mem0-qdrant_i70_t0_async_think5, lme_gptoss20b_rag-pg_i0_t60, lme_gptoss20b_rag-pg_i233_t0, lme_gptoss20b_rag-pg_i233_t0_async_think5, lme_gptoss20b_rag-pg_i366_t0, lme_gptoss20b_rag-pg_i366_t0_async_think5, lme_gptoss20b_rag-pg_i70_t0, lme_gptoss20b_rag-pg_i70_t0_async_think5
- backup: {'mode': 'download+ack', 'ok': True, 'why': '76 acked', 'missing': ['lme_gptoss20b_mem0-pg_i366_t0_async_think5', 'lme_gptoss20b_mem0-qdrant_i366_t0_async_think5', 'lme_gptoss20b_mem0-local_i233_t0_async_think5+late1', 'lme_gptoss20b_mem0-local_i366_t0_async_think5+late1', 'lme_gptoss20b_mem0-local_i70_t0_async_think5+late1', 'lme_gptoss20b_mem0-pg_i233_t0_async_think5+late1', 'lme_gptoss20b_mem0-pg_i366_t0_async_think5+late1', 'lme_gptoss20b_mem0-pg_i70_t0_async_think5+late1', 'lme_gptoss20b_mem0-qdrant_i233_t0_async_think5+late1', 'lme_gptoss20b_mem0-qdrant_i366_t0_async_think5+late1', 'lme_gptoss20b_mem0-qdrant_i70_t0_async_think5+late1', 'lme_gptoss20b_rag-pg_i233_t0_async_think5+late1', 'lme_gptoss20b_rag-pg_i366_t0_async_think5+late1', 'lme_gptoss20b_rag-pg_i70_t0_async_think5+late1']}
- stop: None; 4.26 h since start, cap 5.0 h
- disk free 219.9 GB, RAM avail 46.9 GB, GPU NVIDIA L4, 0 %, 16086 MiB, 23034 MiB, 35.20 W

## problems

none

## supervisor events

    [2026-11-27 21:17:37Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 723
    [2026-11-27 21:32:58Z] setup attempt 1: rc=0 in 15.1 min
    [2026-11-27 21:32:58Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme', 'kprof # retry', 'l1 # async retry', 'score budget # after async l1 retry', 'lme # async retry', 'score budget # after async lme retry']
    [2026-11-27 21:32:59Z] start 'lme # async retry' attempt 1/3 at 92c3106 Colab status at runtime 1 release
    [2026-11-28 01:31:00Z] finished 'lme # async retry'
    [2026-11-28 01:31:04Z] start 'score budget # after async lme retry' attempt 1/3 at 4da3040 Colab: async lme i366 progress (runtime 2)
    [2026-11-28 01:31:34Z] finished 'score budget # after async lme retry'
    [2026-11-28 01:31:34Z] queue empty at 4da3040 Colab: async lme i366 progress (runtime 2); waiting up to 15 min for new lines in colab/queue.txt

## suite.log (tail)

    embedder (Qwen3-Embedding-0.6B-Q8_0.gguf) up
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.543783187866211, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [21:33:08] skip lme_gptoss20b_rag-pg_i70_t0_async_think5
    [21:33:08] skip lme_gptoss20b_mem0-local_i70_t0_async_think5
    [21:33:08] skip lme_gptoss20b_mem0-pg_i70_t0_async_think5
    [21:33:08] skip lme_gptoss20b_mem0-qdrant_i70_t0_async_think5
    [21:33:08] skip lme_gptoss20b_rag-pg_i233_t0_async_think5
    [21:33:08] === lme_gptoss20b_mem0-local_i233_t0_async_think5 (mem0-local) PROFILE=gptoss20b
    [22:08:43] done lme_gptoss20b_mem0-local_i233_t0_async_think5: {"n_turns": 240, "n_qa": 1, "count": 833, "total_s": 2111.303919627}
    [22:08:43] === lme_gptoss20b_mem0-pg_i233_t0_async_think5 (mem0-pg) PROFILE=gptoss20b
    [22:44:01] done lme_gptoss20b_mem0-pg_i233_t0_async_think5: {"n_turns": 240, "n_qa": 1, "count": 870, "total_s": 2082.0570027980007}
    [22:44:01] === lme_gptoss20b_mem0-qdrant_i233_t0_async_think5 (mem0-qdrant) PROFILE=gptoss20b
    [23:18:01] done lme_gptoss20b_mem0-qdrant_i233_t0_async_think5: {"n_turns": 240, "n_qa": 1, "count": 843, "total_s": 2005.1665667509997}
    [23:18:01] === lme_gptoss20b_rag-pg_i366_t0_async_think5 (rag-pg) PROFILE=gptoss20b
    [23:53:43] done lme_gptoss20b_rag-pg_i366_t0_async_think5: {"n_turns": 205, "n_qa": 1, "count": 205, "total_s": 2108.3020169769998}
    [23:53:43] === lme_gptoss20b_mem0-local_i366_t0_async_think5 (mem0-local) PROFILE=gptoss20b
    [00:27:28] done lme_gptoss20b_mem0-local_i366_t0_async_think5: {"n_turns": 205, "n_qa": 1, "count": 740, "total_s": 1991.4721360290005}
    [00:27:28] === lme_gptoss20b_mem0-pg_i366_t0_async_think5 (mem0-pg) PROFILE=gptoss20b
    [00:59:05] done lme_gptoss20b_mem0-pg_i366_t0_async_think5: {"n_turns": 205, "n_qa": 1, "count": 734, "total_s": 1861.3966928659993}
    [00:59:05] === lme_gptoss20b_mem0-qdrant_i366_t0_async_think5 (mem0-qdrant) PROFILE=gptoss20b
    [01:30:31] done lme_gptoss20b_mem0-qdrant_i366_t0_async_think5: {"n_turns": 205, "n_qa": 1, "count": 791, "total_s": 1852.326594006001}
    [01:30:31] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 8.351725578308105, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    lme_gptoss20b_mem0-local_i233_t0_async_think5: n=1 F1=0.039 J=0.000
    lme_gptoss20b_mem0-local_i366_t0_async_think5: n=1 F1=0.421 J=1.000
    lme_gptoss20b_mem0-local_i70_t0_async_think5: n=1 F1=0.000 J=0.000
    lme_gptoss20b_mem0-pg_i233_t0_async_think5: n=1 F1=0.044 J=0.000
    lme_gptoss20b_mem0-pg_i366_t0_async_think5: n=1 F1=0.000 J=0.000
    lme_gptoss20b_mem0-pg_i70_t0_async_think5: n=1 F1=0.000 J=0.000
    lme_gptoss20b_mem0-qdrant_i233_t0_async_think5: n=1 F1=0.039 J=0.000
    lme_gptoss20b_mem0-qdrant_i366_t0_async_think5: n=1 F1=0.000 J=0.000
    lme_gptoss20b_mem0-qdrant_i70_t0_async_think5: n=1 F1=0.000 J=0.000
    lme_gptoss20b_rag-pg_i233_t0_async_think5: n=1 F1=0.037 J=0.000
    lme_gptoss20b_rag-pg_i366_t0_async_think5: n=1 F1=0.000 J=0.000
    lme_gptoss20b_rag-pg_i70_t0_async_think5: n=1 F1=0.054 J=1.000
    [01:31:23] suite done -> /content/results/L4
