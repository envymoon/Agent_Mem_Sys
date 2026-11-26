| run | system | dataset | n QA | F1 | judge acc |
|---|---|---|---|---|---|
| l1_gptoss20b_graphiti_sync_t20 | graphiti | locomo | 10 | 0.046 | 0.100 |
| l1_gptoss20b_mem0-local_sync_t20 | mem0-local | locomo | 10 | 0.119 | 0.600 |
| l1_gptoss20b_mem0-pg_sync_t20 | mem0-pg | locomo | 10 | 0.113 | 0.600 |
| l1_gptoss20b_mem0-qdrant_sync_t20 | mem0-qdrant | locomo | 10 | 0.134 | 0.600 |
| l1_gptoss20b_rag-pg_sync_t20 | rag-pg | locomo | 10 | 0.163 | 0.800 |
| lme_gptoss20b_graphiti_i0_t60 | graphiti | longmemeval | 1 | 0.444 | 1.000 |
| lme_gptoss20b_mem0-local_i0_t60 | mem0-local | longmemeval | 1 | 0.444 | 1.000 |
| lme_gptoss20b_mem0-pg_i0_t60 | mem0-pg | longmemeval | 1 | 0.444 | 1.000 |
| lme_gptoss20b_mem0-qdrant_i0_t60 | mem0-qdrant | longmemeval | 1 | 0.444 | 1.000 |
| lme_gptoss20b_rag-pg_i0_t60 | rag-pg | longmemeval | 1 | 0.000 | 0.000 |

| system | dataset | runs | n QA | F1 (QA-weighted) | judge acc (QA-weighted) |
|---|---|---|---|---|---|
| graphiti | locomo | 1 | 10 | 0.046 | 0.100 |
| graphiti | longmemeval | 1 | 1 | 0.444 | 1.000 |
| mem0-local | locomo | 1 | 10 | 0.119 | 0.600 |
| mem0-local | longmemeval | 1 | 1 | 0.444 | 1.000 |
| mem0-pg | locomo | 1 | 10 | 0.113 | 0.600 |
| mem0-pg | longmemeval | 1 | 1 | 0.444 | 1.000 |
| mem0-qdrant | locomo | 1 | 10 | 0.134 | 0.600 |
| mem0-qdrant | longmemeval | 1 | 1 | 0.444 | 1.000 |
| rag-pg | locomo | 1 | 10 | 0.163 | 0.800 |
| rag-pg | longmemeval | 1 | 1 | 0.000 | 0.000 |
