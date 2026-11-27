### kprof_gptoss20b_mem0-pg_async_think5  turns [10, 13]: 531205 kernels, 11570 ms kernel time in 16251 ms (alignment: 99.9% inside LLM calls)

| stage | wall ms | kernel ms | GPU busy | top categories |
|---|---|---|---|---|
| memory:reasoning | 9355 | 4453 | 48% | matmul (quantized, other) 41%, matmul MoE experts (MXFP4) 41%, flash attention 9%, activation quantize 2% |
| memory:answer | 4441 | 3227 | 73% | matmul MoE experts (MXFP4) 41%, matmul (quantized, other) 41%, flash attention 9%, activation quantize 2% |
| agent:answer | 1191 | 1013 | 85% | matmul (quantized, other) 44%, matmul MoE experts (MXFP4) 44%, flash attention 3%, activation quantize 2% |
| memory:prefill | 1350 | 936 | 69% | matmul MoE experts (MXFP4) 60%, matmul (quantized, other) 16%, flash attention 12%, elementwise (add/mul/glu/...) 6% |
| agent:prefill | 703 | 623 | 89% | matmul MoE experts (MXFP4) 71%, matmul (quantized, other) 17%, elementwise (add/mul/glu/...) 4%, flash attention 3% |
| agent:prefill+memory:answer | 407 | 359 | 88% | matmul MoE experts (MXFP4) 66%, matmul (quantized, other) 17%, flash attention 9%, elementwise (add/mul/glu/...) 4% |
| agent:reasoning | 337 | 292 | 87% | matmul (quantized, other) 44%, matmul MoE experts (MXFP4) 44%, flash attention 3%, activation quantize 2% |
| agent:answer+memory:answer | 234 | 200 | 86% | matmul MoE experts (MXFP4) 55%, matmul (quantized, other) 30%, flash attention 7%, elementwise (add/mul/glu/...) 2% |
| agent:reasoning+memory:answer | 215 | 184 | 86% | matmul MoE experts (MXFP4) 55%, matmul (quantized, other) 29%, flash attention 7%, elementwise (add/mul/glu/...) 2% |
| memory:queue | 461 | 105 | 23% | matmul MoE experts (MXFP4) 65%, matmul (quantized, other) 16%, flash attention 9%, elementwise (add/mul/glu/...) 4% |
| agent:queue+memory:answer | 103 | 92 | 89% | matmul MoE experts (MXFP4) 63%, matmul (quantized, other) 23%, flash attention 7%, elementwise (add/mul/glu/...) 3% |
| agent:queue | 354 | 70 | 20% | matmul MoE experts (MXFP4) 82%, matmul (quantized, other) 11%, elementwise (add/mul/glu/...) 4%, flash attention 1% |
| none | 2302 | 14 | 1% | matmul (quantized, other) 100% |

| category | ms | share |
|---|---|---|
| matmul MoE experts (MXFP4) | 5376 | 46.5% |
| matmul (quantized, other) | 4226 | 36.5% |
| flash attention | 903 | 7.8% |
| activation quantize | 199 | 1.7% |
| elementwise (add/mul/glu/...) | 188 | 1.6% |
| router / softmax / top-k | 184 | 1.6% |
| norm | 136 | 1.2% |
| matmul (f16/f32 / cuBLAS) | 87 | 0.7% |
| rope | 86 | 0.7% |
| KV cache write / copy | 78 | 0.7% |
| other | 58 | 0.5% |
| gather / get_rows | 50 | 0.4% |
