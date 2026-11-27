# L4  2026-11-27 16:41:45Z  (running)

- code `a321a0a Fix LLM launcher aborting under set -e when nsys is installed (nsys shutdown with no session); requeue async + kprof lines`, runtime up 0.66 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme', 'kprof # retry', 'l1 # async retry', 'score budget # after async l1 retry', 'lme # async retry', 'score budget # after async lme retry']  done: ['pilot', 'l1', 'score budget # after l1', 'lme', 'score budget # after lme']  gave up: ['kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme']
- now: line `kprof # retry` attempt 1, run `None`, suite alive True, last write 4.3 min ago
- finished runs (27): l1_gptoss20b_graphiti_sync_t100, l1_gptoss20b_graphiti_sync_t20, l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-local_sync_t20, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_mem0-pg_sync_t20, l1_gptoss20b_mem0-qdrant_sync_t100, l1_gptoss20b_mem0-qdrant_sync_t20, l1_gptoss20b_rag-pg_sync_t100, l1_gptoss20b_rag-pg_sync_t20, lme_gptoss20b_graphiti_i0_t60, lme_gptoss20b_mem0-local_i0_t60, lme_gptoss20b_mem0-local_i233_t0, lme_gptoss20b_mem0-local_i366_t0, lme_gptoss20b_mem0-local_i70_t0, lme_gptoss20b_mem0-pg_i0_t60, lme_gptoss20b_mem0-pg_i233_t0, lme_gptoss20b_mem0-pg_i366_t0, lme_gptoss20b_mem0-pg_i70_t0, lme_gptoss20b_mem0-qdrant_i0_t60, lme_gptoss20b_mem0-qdrant_i233_t0, lme_gptoss20b_mem0-qdrant_i366_t0, lme_gptoss20b_mem0-qdrant_i70_t0, lme_gptoss20b_rag-pg_i0_t60, lme_gptoss20b_rag-pg_i233_t0, lme_gptoss20b_rag-pg_i366_t0, lme_gptoss20b_rag-pg_i70_t0
- backup: {'mode': 'download+ack', 'ok': True, 'why': '49 acked', 'missing': []}
- stop: None; 0.62 h since start, cap 5.0 h
- disk free 220.8 GB, RAM avail 50.0 GB, GPU NVIDIA L4, 0 %, 3968 MiB, 23034 MiB, 32.42 W

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

## supervisor events

    [2026-11-27 16:04:52Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 697
    [2026-11-27 16:21:44Z] setup attempt 1: rc=0 in 16.7 min
    [2026-11-27 16:21:45Z] supervisor up: OUT=/content/results/L4 SYNC= queue=['l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'kprof', 'l1 # async', 'score budget # after async l1', 'lme # async', 'score budget # after async lme']
    [2026-11-27 16:21:45Z] start 'kprof' attempt 1/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:25:15Z] 'kprof' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:25:16Z] start 'kprof' attempt 2/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
    [2026-11-27 16:25:46Z] 'kprof' attempt ended rc=1; failed runs: ['(stack) LLM failed: ']
    [2026-11-27 16:25:46Z] start 'kprof' attempt 3/3 at c11e895 Kernel-level GPU profiling (Nsight Systems window on the LLM server + kernel classification and attribution to request stages; Nsight Compute speed-of-light probe), async write path as the l1/lme default, patrol fetches queue_state.json
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

## suite.log (tail)

    [16:23:01] kprof ncu tg: rc=0 
    [16:25:00] kprof ncu pp: rc=0 
    embedder (Qwen3-Embedding-0.6B-Q8_0.gguf) up
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
    /root/llama.cpp/build/bin/llama-server -m /root/models/gpt-oss-20b-MXFP4.gguf --alias local --port 8000 --host 127.0.0.1 -c 32768 -np 2 -ngl 99 -ctk f16 -ctv f16 -fa on --fit off --kv-unified --cache-ram 8192 --slot-save-path /opt/svc/data/kv_slots/ --metrics --jinja --no-webui -t 12 -lv 4 --load-mode auto
    nsys: nsys launch --session-new=memprof --trace=cuda --sample=none --cpuctxsw=none
