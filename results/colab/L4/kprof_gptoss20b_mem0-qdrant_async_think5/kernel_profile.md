### kprof_gptoss20b_mem0-qdrant_async_think5  turns [10, 13]: 770625 kernels, 16283 ms kernel time in 19921 ms (alignment: 99.6% inside LLM calls)

| stage | wall ms | kernel ms | GPU busy | top categories |
|---|---|---|---|---|
| memory:reasoning | 17120 | 9818 | 57% | matmul MoE experts (MXFP4) 41%, matmul (quantized, other) 41%, flash attention 9%, activation quantize 2% |
| memory:answer | 5420 | 2393 | 44% | matmul (quantized, other) 41%, matmul MoE experts (MXFP4) 41%, flash attention 9%, activation quantize 2% |
| agent:answer+memory:reasoning | 1854 | 1579 | 85% | matmul MoE experts (MXFP4) 54%, matmul (quantized, other) 30%, flash attention 7%, elementwise (add/mul/glu/...) 2% |
| agent:reasoning+memory:reasoning | 804 | 684 | 85% | matmul MoE experts (MXFP4) 55%, matmul (quantized, other) 30%, flash attention 7%, elementwise (add/mul/glu/...) 2% |
| agent:prefill+memory:reasoning | 559 | 489 | 88% | matmul MoE experts (MXFP4) 66%, matmul (quantized, other) 17%, flash attention 9%, elementwise (add/mul/glu/...) 4% |
| agent:reasoning+memory:prefill | 381 | 341 | 90% | matmul MoE experts (MXFP4) 62%, matmul (quantized, other) 15%, flash attention 12%, elementwise (add/mul/glu/...) 6% |
| memory:queue | 622 | 239 | 38% | matmul MoE experts (MXFP4) 65%, matmul (quantized, other) 12%, flash attention 11%, elementwise (add/mul/glu/...) 8% |
| agent:prefill+memory:prefill | 232 | 213 | 92% | matmul MoE experts (MXFP4) 67%, matmul (quantized, other) 14%, flash attention 10%, elementwise (add/mul/glu/...) 5% |
| agent:prefill | 173 | 166 | 95% | matmul MoE experts (MXFP4) 71%, matmul (quantized, other) 13%, elementwise (add/mul/glu/...) 8%, flash attention 3% |
| agent:queue+memory:prefill | 116 | 104 | 90% | matmul MoE experts (MXFP4) 65%, matmul (quantized, other) 14%, flash attention 11%, elementwise (add/mul/glu/...) 6% |
| agent:queue+memory:reasoning | 107 | 88 | 83% | matmul MoE experts (MXFP4) 52%, matmul (quantized, other) 33%, flash attention 8%, elementwise (add/mul/glu/...) 2% |
| agent:reasoning+memory:queue | 124 | 63 | 50% | matmul MoE experts (MXFP4) 48%, matmul (quantized, other) 40%, flash attention 4%, activation quantize 2% |
| none | 1014 | 58 | 6% | matmul (quantized, other) 46%, matmul MoE experts (MXFP4) 38%, flash attention 8%, activation quantize 2% |
| agent:prefill+memory:queue | 56 | 40 | 72% | matmul MoE experts (MXFP4) 66%, matmul (quantized, other) 23%, flash attention 2%, elementwise (add/mul/glu/...) 2% |
| agent:queue+memory:queue | 6 | 6 | 111% | matmul MoE experts (MXFP4) 80%, matmul (quantized, other) 7%, elementwise (add/mul/glu/...) 7%, flash attention 3% |
| agent:queue | 188 | 2 | 1% | KV cache write / copy 57%, matmul (quantized, other) 26%, flash attention 7%, elementwise (add/mul/glu/...) 3% |

| category | ms | share |
|---|---|---|
| matmul MoE experts (MXFP4) | 7416 | 45.5% |
| matmul (quantized, other) | 6014 | 36.9% |
| flash attention | 1386 | 8.5% |
| activation quantize | 291 | 1.8% |
| router / softmax / top-k | 263 | 1.6% |
| elementwise (add/mul/glu/...) | 236 | 1.4% |
| norm | 190 | 1.2% |
| matmul (f16/f32 / cuBLAS) | 120 | 0.7% |
| rope | 112 | 0.7% |
| KV cache write / copy | 111 | 0.7% |
| other | 74 | 0.5% |
| gather / get_rows | 69 | 0.4% |
