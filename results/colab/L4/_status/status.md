# L4  2026-11-27 06:43:03Z  (running)

- code `39d46ab Colab layer 1: rag-pg and mem0 l1 t100 runs fetched`, runtime up 3.18 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme']  done: ['l1', 'score budget # after l1']  gave up: []
- now: line `lme` attempt 1, run `lme_gptoss20b_mem0-qdrant_i70_t0`, suite alive True, last write 0.0 min ago
- finished runs (5): l1_gptoss20b_graphiti_sync_t100, l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_mem0-qdrant_sync_t100, l1_gptoss20b_rag-pg_sync_t100
- backup: {'mode': 'download+ack', 'ok': True, 'why': '25 acked', 'missing': []}
- stop: None; 3.13 h since start, cap 5.0 h
- disk free 220.4 GB, RAM avail 39.2 GB, GPU NVIDIA L4, 90 %, 14296 MiB, 23034 MiB, 66.77 W

## problems

    [05:19:25] FAILED lme_gptoss20b_rag-pg_i70_t0 rc=1:   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/openai/_base_client.py", line 1248, in request     raise self._make_status_error_from_response(err.response) from None openai.BadRequestError: Error code: 400 - request (4066 tokens) exceeds the available context size (2048 tokens), t
    [06:01:07] FAILED lme_gptoss20b_mem0-local_i70_t0 rc=1:   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/qdrant_client/qdrant_client.py", line 181, in close   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/qdrant_client/local/qdrant_local.py", line 113, in close ImportError: sys.meta_path is None, Python is likely shutti
    [06:37:22] FAILED lme_gptoss20b_mem0-pg_i70_t0 rc=1:   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/openai/_base_client.py", line 1248, in request     raise self._make_status_error_from_response(err.response) from None openai.BadRequestError: Error code: 400 - request (4067 tokens) exceeds the available context size (2048 tokens), t

## supervisor events

    [2026-11-27 03:35:39Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 780
    [2026-11-27 03:53:02Z] setup attempt 1: rc=0 in 17.4 min
    [2026-11-27 03:53:02Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['l1', 'score budget # after l1', 'lme', 'score budget # after lme']
    [2026-11-27 03:53:03Z] start 'l1' attempt 1/3 at 821542b Colab status: layer-1 runtime building llama.cpp
    [2026-11-27 05:00:33Z] finished 'l1'
    [2026-11-27 05:00:35Z] start 'score budget # after l1' attempt 1/3 at 39d46ab Colab layer 1: rag-pg and mem0 l1 t100 runs fetched
    [2026-11-27 05:04:05Z] finished 'score budget # after l1'
    [2026-11-27 05:04:05Z] start 'lme' attempt 1/3 at 39d46ab Colab layer 1: rag-pg and mem0 l1 t100 runs fetched

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
    [04:30:10] done l1_gptoss20b_mem0-qdrant_sync_t100: {"n_turns": 100, "n_qa": 47, "count": 144, "total_s": 657.2621116169998}
    [04:30:10] === l1_gptoss20b_graphiti_sync_t100 (graphiti) PROFILE=gptoss20b
    [05:00:20] done l1_gptoss20b_graphiti_sync_t100: {"n_turns": 100, "n_qa": 47, "count": 115, "total_s": 1778.9128988410002}
    [05:00:20] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 8.387088060379028, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    l1_gptoss20b_graphiti_sync_t100: n=47 F1=0.127 J=0.298
    l1_gptoss20b_mem0-local_sync_t100: n=47 F1=0.172 J=0.574
    l1_gptoss20b_mem0-pg_sync_t100: n=47 F1=0.162 J=0.553
    l1_gptoss20b_mem0-qdrant_sync_t100: n=47 F1=0.161 J=0.596
    l1_gptoss20b_rag-pg_sync_t100: n=47 F1=0.198 J=0.511
    [05:03:36] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.1165854930877686, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [05:04:11] === lme_gptoss20b_rag-pg_i70_t0 (rag-pg) PROFILE=gptoss20b
    [05:19:25] FAILED lme_gptoss20b_rag-pg_i70_t0 rc=1:   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/openai/_base_client.py", line 1248, in request     raise self._make_status_error_from_response(err.response) from None openai.BadRequestError: Error code: 400 - request (4066 tokens) exceeds the available context size (2048 tokens), t
    [05:19:25] === lme_gptoss20b_mem0-local_i70_t0 (mem0-local) PROFILE=gptoss20b
    [06:01:07] FAILED lme_gptoss20b_mem0-local_i70_t0 rc=1:   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/qdrant_client/qdrant_client.py", line 181, in close   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/qdrant_client/local/qdrant_local.py", line 113, in close ImportError: sys.meta_path is None, Python is likely shutti
    [06:01:07] === lme_gptoss20b_mem0-pg_i70_t0 (mem0-pg) PROFILE=gptoss20b
    [06:37:22] FAILED lme_gptoss20b_mem0-pg_i70_t0 rc=1:   File "/content/Agent_Mem_Sys/.venv/lib/python3.12/site-packages/openai/_base_client.py", line 1248, in request     raise self._make_status_error_from_response(err.response) from None openai.BadRequestError: Error code: 400 - request (4067 tokens) exceeds the available context size (2048 tokens), t
    [06:37:22] === lme_gptoss20b_mem0-qdrant_i70_t0 (mem0-qdrant) PROFILE=gptoss20b
