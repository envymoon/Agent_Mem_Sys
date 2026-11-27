# L4  2026-11-27 18:34:53Z  (running)

- code `e9dd87b Colab: kprof done for 4 systems; first async l1 runs (rag-pg, mem0-local)`, runtime up 2.54 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme', 'kprof # retry', 'l1 # async retry', 'score budget # after async l1 retry', 'lme # async retry', 'score budget # after async lme retry']  done: ['pilot', 'l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'kprof # retry', 'l1 # async retry', 'score budget # after async l1 retry']  gave up: ['kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme']
- now: line `lme # async retry` attempt 1, run `lme_gptoss20b_mem0-local_i70_t0_async_think5`, suite alive True, last write 0.1 min ago
- finished runs (36): kprof_gptoss20b_mem0-local_async_think5, kprof_gptoss20b_mem0-pg_async_think5, kprof_gptoss20b_mem0-qdrant_async_think5, kprof_gptoss20b_rag-pg_async_think5, l1_gptoss20b_graphiti_sync_t100, l1_gptoss20b_graphiti_sync_t20, l1_gptoss20b_mem0-local_async_think5_t100, l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-local_sync_t20, l1_gptoss20b_mem0-pg_async_think5_t100, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_mem0-pg_sync_t20, l1_gptoss20b_mem0-qdrant_async_think5_t100, l1_gptoss20b_mem0-qdrant_sync_t100, l1_gptoss20b_mem0-qdrant_sync_t20, l1_gptoss20b_rag-pg_async_think5_t100, l1_gptoss20b_rag-pg_sync_t100, l1_gptoss20b_rag-pg_sync_t20, lme_gptoss20b_graphiti_i0_t60, lme_gptoss20b_mem0-local_i0_t60, lme_gptoss20b_mem0-local_i233_t0, lme_gptoss20b_mem0-local_i366_t0, lme_gptoss20b_mem0-local_i70_t0, lme_gptoss20b_mem0-pg_i0_t60, lme_gptoss20b_mem0-pg_i233_t0, lme_gptoss20b_mem0-pg_i366_t0, lme_gptoss20b_mem0-pg_i70_t0, lme_gptoss20b_mem0-qdrant_i0_t60, lme_gptoss20b_mem0-qdrant_i233_t0, lme_gptoss20b_mem0-qdrant_i366_t0, lme_gptoss20b_mem0-qdrant_i70_t0, lme_gptoss20b_rag-pg_i0_t60, lme_gptoss20b_rag-pg_i233_t0, lme_gptoss20b_rag-pg_i366_t0, lme_gptoss20b_rag-pg_i70_t0, lme_gptoss20b_rag-pg_i70_t0_async_think5
- backup: {'mode': 'download+ack', 'ok': True, 'why': '56 acked', 'missing': ['l1_gptoss20b_mem0-pg_async_think5_t100', 'l1_gptoss20b_mem0-qdrant_async_think5_t100', 'lme_gptoss20b_rag-pg_i70_t0_async_think5', 'kprof_gptoss20b_mem0-local_async_think5+late1', 'kprof_gptoss20b_mem0-pg_async_think5+late1', 'kprof_gptoss20b_mem0-qdrant_async_think5+late1', 'kprof_gptoss20b_rag-pg_async_think5+late1', 'l1_gptoss20b_mem0-local_async_think5_t100+late1', 'l1_gptoss20b_mem0-pg_async_think5_t100+late1', 'l1_gptoss20b_mem0-qdrant_async_think5_t100+late1', 'l1_gptoss20b_rag-pg_async_think5_t100+late1']}
- stop: None; 2.51 h since start, cap 5.0 h
- disk free 219.7 GB, RAM avail 38.5 GB, GPU NVIDIA L4, 90 %, 16092 MiB, 23034 MiB, 72.20 W

## problems

    [16:25:03] LLM failed: 
    [16:25:16] LLM failed: 
    [16:25:47] LLM failed: 
    [16:26:17] LLM failed: 
    [16:26:48] LLM failed: 
    [16:27:18] LLM failed: 
    [16:27:49] LLM failed: 
    [16:28:20] LLM failed: 
    [16:28:50] LLM failed: 
    [16:29:21] LLM failed: 
    [16:29:52] LLM failed: 
    [16:30:22] LLM failed: 
    [16:30:53] LLM failed: 
    [16:31:23] LLM failed: 
    [16:31:54] LLM failed: 
    [16:47:52] LLM failed: ERROR: The --cpuctxsw switch is not supported by the launch command after NVIDIA Nsight Systems v2021.5.

## supervisor events

    [2026-11-27 16:26:16Z] 'kprof' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:26:16Z] GAVE UP 'kprof' after 3 attempts (fix + append a '# retry' line to colab/queue.txt)
    [2026-11-27 16:26:17Z] start 'l1 # async' attempt 1/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:26:47Z] 'l1 # async' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:26:48Z] start 'l1 # async' attempt 2/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:27:18Z] 'l1 # async' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:27:18Z] start 'l1 # async' attempt 3/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:27:48Z] 'l1 # async' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:27:48Z] GAVE UP 'l1 # async' after 3 attempts (fix + append a '# retry' line to colab/queue.txt)
    [2026-11-27 16:27:49Z] start 'score budget # after async l1' attempt 1/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:28:19Z] 'score budget # after async l1' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:28:20Z] start 'score budget # after async l1' attempt 2/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:28:50Z] 'score budget # after async l1' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:28:50Z] start 'score budget # after async l1' attempt 3/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:29:20Z] 'score budget # after async l1' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:29:20Z] GAVE UP 'score budget # after async l1' after 3 attempts (fix + append a '# retry' line to colab/queue.txt)
    [2026-11-27 16:29:21Z] start 'lme # async' attempt 1/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:29:51Z] 'lme # async' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:29:51Z] start 'lme # async' attempt 2/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:30:21Z] 'lme # async' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:30:22Z] start 'lme # async' attempt 3/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:30:52Z] 'lme # async' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:30:52Z] GAVE UP 'lme # async' after 3 attempts (fix + append a '# retry' line to colab/queue.txt)
    [2026-11-27 16:30:53Z] start 'score budget # after async lme' attempt 1/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:31:23Z] 'score budget # after async lme' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:31:23Z] start 'score budget # after async lme' attempt 2/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:31:53Z] 'score budget # after async lme' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:31:54Z] start 'score budget # after async lme' attempt 3/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:32:24Z] 'score budget # after async lme' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:32:24Z] GAVE UP 'score budget # after async lme' after 3 attempts (fix + append a '# retry' line to colab/queue.txt)
    [2026-11-27 16:32:25Z] queue empty at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json; waiting up to 15 min for new lines in colab/queue.txt
    [2026-11-27 16:37:26Z] start 'kprof # retry' attempt 1/3 at a321a0a Fix LLM launcher aborting under set -e when nsys is installed (nsys shutdown with no session); requeue async + kprof lines
    [2026-11-27 16:47:56Z] 'kprof # retry' attempt ended rc=1; failed runs: ['(stack) LLM failed: ERROR: The --cpuctxsw switch is not supported by the launch command ']
    [2026-11-27 16:47:57Z] start 'kprof # retry' attempt 2/3 at 41ac3ad Colab status snapshot
    [2026-11-27 17:00:57Z] finished 'kprof # retry'
    [2026-11-27 17:00:58Z] start 'l1 # async retry' attempt 1/3 at b98367e kernel_profile: Q8_0 dense matmuls (attention projections, output head) get their own category; first kprof runs + Nsight Compute speed-of-light results
    [2026-11-27 17:49:58Z] finished 'l1 # async retry'
    [2026-11-27 17:50:00Z] start 'score budget # after async l1 retry' attempt 1/3 at e9dd87b Colab: kprof done for 4 systems; first async l1 runs (rag-pg, mem0-local)
    [2026-11-27 17:53:00Z] finished 'score budget # after async l1 retry'
    [2026-11-27 17:53:01Z] start 'lme # async retry' attempt 1/3 at e9dd87b Colab: kprof done for 4 systems; first async l1 runs (rag-pg, mem0-local)

## suite.log (tail)

    [16:31:54] LLM failed: 
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    nsys: nsys launch --session-new=memprof --trace=cuda --sample=none --cpuctxsw=none
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) FAILED
    ERROR: The --cpuctxsw switch is not supported by the launch command after NVIDIA Nsight Systems v2021.5.
    The cpuctxsw switch can be set on the profile and start commands.
    [16:47:52] LLM failed: ERROR: The --cpuctxsw switch is not supported by the launch command after NVIDIA Nsight Systems v2021.5.
    The cpuctxsw switch can be set on the profile and start commands.
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    nsys: no --cuda-graph-trace; GGML_CUDA_DISABLE_GRAPHS=1
    nsys: nsys launch --session-new=memprof --trace=cuda
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.7789740562438965, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [16:48:04] === kprof_gptoss20b_rag-pg_async_think5 (rag-pg) PROFILE=gptoss20b
    [16:50:08] done kprof_gptoss20b_rag-pg_async_think5: {"n_turns": 16, "n_qa": 0, "count": 16, "total_s": 104.7535581269999}
    [16:50:17] === kprof_gptoss20b_mem0-local_async_think5 (mem0-local) PROFILE=gptoss20b
    [16:52:53] done kprof_gptoss20b_mem0-local_async_think5: {"n_turns": 16, "n_qa": 0, "count": 24, "total_s": 125.29743097500022}
    [16:53:42] === kprof_gptoss20b_mem0-pg_async_think5 (mem0-pg) PROFILE=gptoss20b
    [16:56:12] done kprof_gptoss20b_mem0-pg_async_think5: {"n_turns": 16, "n_qa": 0, "count": 27, "total_s": 119.78962013299997}
    [16:56:52] === kprof_gptoss20b_mem0-qdrant_async_think5 (mem0-qdrant) PROFILE=gptoss20b
    [16:59:32] done kprof_gptoss20b_mem0-qdrant_async_think5: {"n_turns": 16, "n_qa": 0, "count": 25, "total_s": 128.84415827299972}
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 7.948768615722656, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [17:00:41] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.104719877243042, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [17:01:04] === l1_gptoss20b_rag-pg_async_think5_t100 (rag-pg) PROFILE=gptoss20b
    [17:13:09] done l1_gptoss20b_rag-pg_async_think5_t100: {"n_turns": 100, "n_qa": 47, "count": 100, "total_s": 693.4257176740002}
    [17:13:09] === l1_gptoss20b_mem0-local_async_think5_t100 (mem0-local) PROFILE=gptoss20b
    [17:25:26] done l1_gptoss20b_mem0-local_async_think5_t100: {"n_turns": 100, "n_qa": 47, "count": 145, "total_s": 706.5055486869996}
    [17:25:26] === l1_gptoss20b_mem0-pg_async_think5_t100 (mem0-pg) PROFILE=gptoss20b
    [17:37:37] done l1_gptoss20b_mem0-pg_async_think5_t100: {"n_turns": 100, "n_qa": 47, "count": 151, "total_s": 701.0152497769996}
    [17:37:37] === l1_gptoss20b_mem0-qdrant_async_think5_t100 (mem0-qdrant) PROFILE=gptoss20b
    [17:49:45] done l1_gptoss20b_mem0-qdrant_async_think5_t100: {"n_turns": 100, "n_qa": 47, "count": 137, "total_s": 698.1117209040003}
    [17:49:45] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 8.362060785293579, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    kprof_gptoss20b_mem0-local_async_think5: n=0 F1=0.000 J=0.000
    kprof_gptoss20b_mem0-pg_async_think5: n=0 F1=0.000 J=0.000
    kprof_gptoss20b_mem0-qdrant_async_think5: n=0 F1=0.000 J=0.000
    kprof_gptoss20b_rag-pg_async_think5: n=0 F1=0.000 J=0.000
    l1_gptoss20b_mem0-local_async_think5_t100: n=47 F1=0.166 J=0.596
    l1_gptoss20b_mem0-pg_async_think5_t100: n=47 F1=0.153 J=0.553
    l1_gptoss20b_mem0-qdrant_async_think5_t100: n=47 F1=0.181 J=0.574
    l1_gptoss20b_rag-pg_async_think5_t100: n=47 F1=0.199 J=0.596
    [17:52:34] suite done -> /content/results/L4
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    LLM (gpt-oss-20b-MXFP4.gguf, PROFILE=gptoss20b) up
    {"load_wall_s": 4.085320472717285, "offloaded": "25/25", "buffers_mib": {"model:CPU_Mapped": 586.8, "model:CUDA0": 10949.4, "KV:CUDA0": 786.0, "compute:CUDA0": 123.0, "compute:CUDA_Host": 55.5}, "n_ctx_slot": 32768}
    proxy up
    [17:53:07] === lme_gptoss20b_rag-pg_i70_t0_async_think5 (rag-pg) PROFILE=gptoss20b
    [18:28:29] done lme_gptoss20b_rag-pg_i70_t0_async_think5: {"n_turns": 242, "n_qa": 1, "count": 242, "total_s": 2087.26190418}
    [18:28:29] === lme_gptoss20b_mem0-local_i70_t0_async_think5 (mem0-local) PROFILE=gptoss20b
