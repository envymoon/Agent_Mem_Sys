local disk: 4k write+fsync = 164 us

| run | op | n | LLM calls | prefill / cached / gen tok | measured wall | LLM meas | LLM pred (err) | pred wall (err) | flushes | n*t_commit vs dev flush ms | LLM / storage share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| smoke_graphiti | retrieve | 2 | 0.0 | 0 / 0 / 0 | 146 | 0 | 0 (-) | 146 (+0%) | 0.0 | 0.0 vs 0.0 | 0% / 0.0% |
| smoke_graphiti | generate | 2 | 1.0 | 129 / 58 / 22 | 1402 | 1398 | 1603 (+15%) | 1607 (+15%) | 0.0 | 0.0 vs 0.0 | 100% / 0.0% |
| smoke_graphiti | memorize | 2 | 9.0 | 7536 / 2288 / 927 | 80635 | 78613 | 64268 (-18%) | 66290 (-18%) | 10.0 | 1.6 vs 2.5 | 97% / 0.0% |
| smoke_mem0-local | retrieve | 2 | 0.0 | 0 / 0 / 0 | 110 | 0 | 0 (-) | 110 (+0%) | 0.0 | 0.0 vs 0.0 | 0% / 0.0% |
| smoke_mem0-local | generate | 2 | 1.0 | 136 / 29 / 32 | 2233 | 2230 | 2094 (-6%) | 2097 (-6%) | 0.0 | 0.0 vs 0.0 | 100% / 0.0% |
| smoke_mem0-local | memorize | 2 | 1.0 | 8127 / 0 / 65 | 61401 | 61274 | 59993 (-2%) | 60120 (-2%) | 13.0 | 1.8 vs 2.5 | 100% / 0.0% |
| smoke_mem0-pg | retrieve | 2 | 0.0 | 0 / 0 / 0 | 107 | 0 | 0 (-) | 107 (+0%) | 0.0 | 0.0 vs 0.0 | 0% / 0.0% |
| smoke_mem0-pg | generate | 2 | 1.0 | 140 / 29 / 26 | 1959 | 1956 | 1856 (-5%) | 1859 (-5%) | 0.0 | 0.0 vs 0.0 | 100% / 0.0% |
| smoke_mem0-pg | memorize | 2 | 1.0 | 8135 / 0 / 50 | 59815 | 59614 | 58413 (-2%) | 58615 (-2%) | 15.0 | 2.5 vs 3.5 | 100% / 0.0% |
| smoke_rag-pg | retrieve | 2 | 0.0 | 0 / 0 / 0 | 47 | 0 | 0 (-) | 47 (+0%) | 0.0 | 0.0 vs 0.0 | 0% / 0.0% |
| smoke_rag-pg | generate | 2 | 1.0 | 137 / 60 / 22 | 1525 | 1523 | 1574 (+3%) | 1577 (+3%) | 0.0 | 0.0 vs 0.0 | 100% / 0.0% |
| smoke_rag-pg | memorize | 2 | 0.0 | 0 / 0 / 0 | 131 | 0 | 0 (-) | 131 (-0%) | 1.0 | 0.2 vs 0.0 | 0% / 0.1% |
| ctx16k/smoke_mem0-pg | retrieve | 2 | 0.0 | 0 / 0 / 0 | 101 | 0 | 0 (-) | 101 (+0%) | 0.0 | 0.0 vs 0.0 | 0% / 0.0% |
| ctx16k/smoke_mem0-pg | generate | 2 | 1.0 | 123 / 59 / 22 | 1751 | 1745 | 1638 (-6%) | 1643 (-6%) | 0.0 | 0.0 vs 0.0 | 100% / 0.0% |
| ctx16k/smoke_mem0-pg | memorize | 2 | 1.0 | 189 / 7956 / 107 | 12465 | 12162 | 14253 (+17%) | 14556 (+17%) | 16.5 | 2.7 vs 2.5 | 98% / 0.0% |

what-if (same op counts; LLM part re-costed with the other GPU's rates, storage with the other disk's fsync):
| run | op | scenario | pred wall | speedup vs local | LLM share | storage share | DB share |
|---|---|---|---|---|---|---|---|
| smoke_graphiti | retrieve | local GPU, no KV reuse | 146 | x1.00 | 0% | 0.0% | 69% |
| smoke_graphiti | generate | local GPU, no KV reuse | 1813 | x0.89 | 100% | 0.0% | 0% |
| smoke_graphiti | memorize | local GPU, no KV reuse | 72337 | x0.92 | 97% | 0.0% | 1% |
| smoke_mem0-local | retrieve | local GPU, no KV reuse | 110 | x1.00 | 0% | 0.0% | 2% |
| smoke_mem0-local | generate | local GPU, no KV reuse | 2199 | x0.95 | 100% | 0.0% | 0% |
| smoke_mem0-local | memorize | local GPU, no KV reuse | 60120 | x1.00 | 100% | 0.0% | 0% |
| smoke_mem0-pg | retrieve | local GPU, no KV reuse | 107 | x1.00 | 0% | 0.0% | 6% |
| smoke_mem0-pg | generate | local GPU, no KV reuse | 1961 | x0.95 | 100% | 0.0% | 0% |
| smoke_mem0-pg | memorize | local GPU, no KV reuse | 58615 | x1.00 | 100% | 0.0% | 0% |
| smoke_rag-pg | retrieve | local GPU, no KV reuse | 47 | x1.00 | 0% | 0.0% | 4% |
| smoke_rag-pg | generate | local GPU, no KV reuse | 1786 | x0.88 | 100% | 0.0% | 0% |
| smoke_rag-pg | memorize | local GPU, no KV reuse | 131 | x1.00 | 0% | 0.1% | 2% |
| ctx16k/smoke_mem0-pg | retrieve | local GPU, no KV reuse | 101 | x1.00 | 0% | 0.0% | 6% |
| ctx16k/smoke_mem0-pg | generate | local GPU, no KV reuse | 1851 | x0.89 | 100% | 0.0% | 0% |
| ctx16k/smoke_mem0-pg | memorize | local GPU, no KV reuse | 65292 | x0.22 | 100% | 0.0% | 0% |
