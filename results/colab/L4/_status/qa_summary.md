| run | system | dataset | n QA | F1 | judge acc |
|---|---|---|---|---|---|
| l1_gptoss20b_graphiti_sync_t100 | graphiti | locomo | 47 | 0.127 | 0.298 |
| l1_gptoss20b_mem0-local_sync_t100 | mem0-local | locomo | 47 | 0.172 | 0.574 |
| l1_gptoss20b_mem0-pg_sync_t100 | mem0-pg | locomo | 47 | 0.162 | 0.553 |
| l1_gptoss20b_mem0-qdrant_sync_t100 | mem0-qdrant | locomo | 47 | 0.161 | 0.596 |
| l1_gptoss20b_rag-pg_sync_t100 | rag-pg | locomo | 47 | 0.198 | 0.511 |

| system | dataset | runs | n QA | F1 (QA-weighted) | judge acc (QA-weighted) |
|---|---|---|---|---|---|
| graphiti | locomo | 1 | 47 | 0.127 | 0.298 |
| mem0-local | locomo | 1 | 47 | 0.172 | 0.574 |
| mem0-pg | locomo | 1 | 47 | 0.162 | 0.553 |
| mem0-qdrant | locomo | 1 | 47 | 0.161 | 0.596 |
| rag-pg | locomo | 1 | 47 | 0.198 | 0.511 |
