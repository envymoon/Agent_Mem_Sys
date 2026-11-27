# L4  2026-11-27 15:18:07Z  (finishing: stop requested)

- code `fd59ad3 Profiling: split LLM decode into reasoning vs answer (proxy marks the first answer token; breakdown reports decode_reasoning_ms / decode_answer_ms and token counts); rsplit suite queued`, runtime up 0.18 h
- queue: ['l1', 'score budget # after l1', 'lme', 'score budget # after lme', 'rsplit', 'score budget # after rsplit']  done: ['pilot']  gave up: []
- now: line `None` attempt 0, run `None`, suite alive False, last write 8.8 min ago
- finished runs (27): l1_gptoss20b_graphiti_sync_t100, l1_gptoss20b_graphiti_sync_t20, l1_gptoss20b_mem0-local_sync_t100, l1_gptoss20b_mem0-local_sync_t20, l1_gptoss20b_mem0-pg_sync_t100, l1_gptoss20b_mem0-pg_sync_t20, l1_gptoss20b_mem0-qdrant_sync_t100, l1_gptoss20b_mem0-qdrant_sync_t20, l1_gptoss20b_rag-pg_sync_t100, l1_gptoss20b_rag-pg_sync_t20, lme_gptoss20b_graphiti_i0_t60, lme_gptoss20b_mem0-local_i0_t60, lme_gptoss20b_mem0-local_i233_t0, lme_gptoss20b_mem0-local_i366_t0, lme_gptoss20b_mem0-local_i70_t0, lme_gptoss20b_mem0-pg_i0_t60, lme_gptoss20b_mem0-pg_i233_t0, lme_gptoss20b_mem0-pg_i366_t0, lme_gptoss20b_mem0-pg_i70_t0, lme_gptoss20b_mem0-qdrant_i0_t60, lme_gptoss20b_mem0-qdrant_i233_t0, lme_gptoss20b_mem0-qdrant_i366_t0, lme_gptoss20b_mem0-qdrant_i70_t0, lme_gptoss20b_rag-pg_i0_t60, lme_gptoss20b_rag-pg_i233_t0, lme_gptoss20b_rag-pg_i366_t0, lme_gptoss20b_rag-pg_i70_t0
- backup: {'mode': 'download+ack', 'ok': True, 'why': '0 acked', 'missing': ['l1_gptoss20b_graphiti_sync_t100', 'l1_gptoss20b_graphiti_sync_t20', 'l1_gptoss20b_mem0-local_sync_t100', 'l1_gptoss20b_mem0-local_sync_t20', 'l1_gptoss20b_mem0-pg_sync_t100', 'l1_gptoss20b_mem0-pg_sync_t20', 'l1_gptoss20b_mem0-qdrant_sync_t100', 'l1_gptoss20b_mem0-qdrant_sync_t20', 'l1_gptoss20b_rag-pg_sync_t100', 'l1_gptoss20b_rag-pg_sync_t20', 'lme_gptoss20b_graphiti_i0_t60', 'lme_gptoss20b_mem0-local_i0_t60', 'lme_gptoss20b_mem0-local_i233_t0', 'lme_gptoss20b_mem0-local_i366_t0', 'lme_gptoss20b_mem0-local_i70_t0', 'lme_gptoss20b_mem0-pg_i0_t60', 'lme_gptoss20b_mem0-pg_i233_t0', 'lme_gptoss20b_mem0-pg_i366_t0', 'lme_gptoss20b_mem0-pg_i70_t0', 'lme_gptoss20b_mem0-qdrant_i0_t60', 'lme_gptoss20b_mem0-qdrant_i233_t0', 'lme_gptoss20b_mem0-qdrant_i366_t0', 'lme_gptoss20b_mem0-qdrant_i70_t0', 'lme_gptoss20b_rag-pg_i0_t60', 'lme_gptoss20b_rag-pg_i233_t0', 'lme_gptoss20b_rag-pg_i366_t0', 'lme_gptoss20b_rag-pg_i70_t0']}
- stop: stop requested; 0.14 h since start, cap 5.0 h
- disk free 233.8 GB, RAM avail 49.6 GB, GPU NVIDIA L4, 0 %, 0 MiB, 23034 MiB, 17.12 W

## problems

none

## supervisor events

    [2026-11-27 15:09:50Z] bootstrap: gpu=['NVIDIA L4'] OUT=/content/results/L4 PROFILE=gptoss20b DL_PROFILES=gptoss20b cap=5 h keepalive=pid 697
    [2026-11-27 15:10:50Z] STOP: stop requested
    [2026-11-27 15:11:06Z] finishing (stop requested); waiting up to 75 min for the backup of the last runs

## suite.log (tail)

