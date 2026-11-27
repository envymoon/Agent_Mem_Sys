### kprof_gptoss20b_rag-pg_async_think5  turns [10, 13]: 120559 kernels, 2973 ms kernel time in 13595 ms (alignment: 98.5% inside LLM calls)

| stage | wall ms | kernel ms | GPU busy | top categories |
|---|---|---|---|---|
| agent:answer | 1462 | 1265 | 87% | matmul (quantized, other) 44%, matmul MoE experts (MXFP4) 44%, flash attention 3%, activation quantize 2% |
| agent:prefill | 1291 | 1132 | 88% | matmul MoE experts (MXFP4) 71%, matmul (quantized, other) 16%, elementwise (add/mul/glu/...) 6%, flash attention 3% |
| agent:reasoning | 587 | 510 | 87% | matmul (quantized, other) 44%, matmul MoE experts (MXFP4) 44%, flash attention 3%, activation quantize 2% |
| none | 10035 | 44 | 0% | matmul (quantized, other) 53%, matmul MoE experts (MXFP4) 36%, flash attention 3%, activation quantize 2% |
| agent:queue | 296 | 23 | 8% | matmul MoE experts (MXFP4) 69%, matmul (quantized, other) 14%, elementwise (add/mul/glu/...) 10%, flash attention 2% |

| category | ms | share |
|---|---|---|
| matmul MoE experts (MXFP4) | 1610 | 54.1% |
| matmul (quantized, other) | 984 | 33.1% |
| flash attention | 88 | 2.9% |
| elementwise (add/mul/glu/...) | 83 | 2.8% |
| activation quantize | 41 | 1.4% |
| router / softmax / top-k | 40 | 1.4% |
| norm | 33 | 1.1% |
| rope | 26 | 0.9% |
| matmul (f16/f32 / cuBLAS) | 21 | 0.7% |
| other | 18 | 0.6% |
| KV cache write / copy | 17 | 0.6% |
| gather / get_rows | 12 | 0.4% |
