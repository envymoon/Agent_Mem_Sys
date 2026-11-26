## measured (pilot) per-turn cost, profile gptoss20b

| profile | system | dataset | runs | turns | s/turn first | s/turn growth per turn | s/QA | cold start s |
|---|---|---|---|---|---|---|---|---|
| gptoss20b | graphiti | locomo | 1 | 19 | 8.1 | 0.790 | 1.3 | 3.8 |
| gptoss20b | graphiti | longmemeval | 1 | 63 | 28.9 | 0.191 | 0.8 | 3.5 |
| gptoss20b | mem0-local | locomo | 1 | 19 | 2.4 | 0.361 | 1.2 | 1.7 |
| gptoss20b | mem0-local | longmemeval | 1 | 63 | 8.7 | 0.016 | 0.7 | 1.6 |
| gptoss20b | mem0-pg | locomo | 1 | 19 | 2.2 | 0.343 | 1.0 | 1.5 |
| gptoss20b | mem0-pg | longmemeval | 1 | 63 | 8.1 | 0.002 | 0.7 | 1.5 |
| gptoss20b | mem0-qdrant | locomo | 1 | 19 | 3.2 | 0.236 | 1.2 | 3.7 |
| gptoss20b | mem0-qdrant | longmemeval | 1 | 63 | 8.6 | 0.000 | 0.8 | 3.6 |
| gptoss20b | rag-pg | locomo | 1 | 19 | 0.9 | 0.022 | 1.1 | 1.6 |
| gptoss20b | rag-pg | longmemeval | 1 | 63 | 3.3 | 0.000 | 1.7 | 1.4 |

## projection for the full suites

| suite | what | hours | compute units | note |
|---|---|---|---|---|
| l1 | 5 systems x LoCoMo 100 turns + 50 QA | 3.0 | 7 |  |
| lme | 3 LongMemEval-S haystacks x 5 systems x ~245 turns | 16.9 | 39 | full haystack; growth extrapolated far beyond the pilot -> least certain row |
| l2 | 4 systems x async (think 0 s and 5 s) x 100 turns | 5.5 | 13 | async total ~ sync total (backlog drains at the end) + think time |
| l3 | 2 systems (mem0-pg, graphiti) x 6 KV variants x 60 turns | 4.4 | 10 | costed as the base variant; 'noprefix' and 'ctx8k' are slower (mem0 can be several x) |
| l4 q14b | q14b: mem0-pg + graphiti x 60 turns + 20 QA | 0.7 | 2 | no rates file for this profile yet: costed as the main profile |
| l4 q4b | q4b: mem0-pg + graphiti x 60 turns + 20 QA | 0.7 | 2 | no rates file for this profile yet: costed as the main profile |
| l5 | store scale 1e3..1e5, 4 backends | 1.5 | 3 | LLM-free; embedding + DB only; planning guess |

experiments 32.8 h + setup 4 runtime(s) x 16 min = **33.8 h** = **79 compute units** at 2.33 CU/h
