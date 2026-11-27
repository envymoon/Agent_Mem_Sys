### kprof_gptoss20b_mem0-local_async_think5  turns [10, 13]: 640505 kernels, 13915 ms kernel time in 17720 ms (alignment: 99.9% inside LLM calls)

| stage | wall ms | kernel ms | GPU busy | top categories |
|---|---|---|---|---|
| memory:reasoning | 12800 | 7399 | 58% | matmul (quantized, other) 41%, matmul MoE experts (MXFP4) 41%, flash attention 9%, activation quantize 2% |
| memory:answer | 3072 | 2070 | 67% | matmul (quantized, other) 41%, matmul MoE experts (MXFP4) 41%, flash attention 9%, activation quantize 2% |
| agent:answer+memory:answer | 1214 | 1034 | 85% | matmul MoE experts (MXFP4) 54%, matmul (quantized, other) 30%, flash attention 8%, elementwise (add/mul/glu/...) 2% |
| memory:prefill | 1339 | 917 | 68% | matmul MoE experts (MXFP4) 61%, matmul (quantized, other) 16%, flash attention 12%, elementwise (add/mul/glu/...) 6% |
| agent:prefill+memory:answer | 797 | 702 | 88% | matmul MoE experts (MXFP4) 65%, matmul (quantized, other) 18%, flash attention 9%, elementwise (add/mul/glu/...) 4% |
| agent:answer | 655 | 552 | 84% | matmul (quantized, other) 44%, matmul MoE experts (MXFP4) 43%, flash attention 3%, activation quantize 2% |
| agent:reasoning+memory:answer | 538 | 459 | 85% | matmul MoE experts (MXFP4) 55%, matmul (quantized, other) 29%, flash attention 7%, elementwise (add/mul/glu/...) 2% |
| agent:prefill | 397 | 328 | 83% | matmul MoE experts (MXFP4) 72%, matmul (quantized, other) 17%, elementwise (add/mul/glu/...) 4%, flash attention 3% |
| agent:queue+memory:answer | 224 | 201 | 90% | matmul MoE experts (MXFP4) 63%, matmul (quantized, other) 23%, flash attention 7%, elementwise (add/mul/glu/...) 2% |
| agent:reasoning | 155 | 134 | 87% | matmul (quantized, other) 44%, matmul MoE experts (MXFP4) 44%, flash attention 3%, activation quantize 2% |
| memory:queue | 424 | 88 | 21% | matmul MoE experts (MXFP4) 64%, matmul (quantized, other) 17%, flash attention 9%, elementwise (add/mul/glu/...) 4% |
| agent:queue | 174 | 18 | 10% | matmul MoE experts (MXFP4) 82%, matmul (quantized, other) 10%, elementwise (add/mul/glu/...) 4%, flash attention 1% |
| none | 1135 | 12 | 1% | matmul (quantized, other) 97%, matmul MoE experts (MXFP4) 2%, activation quantize 0%, norm 0% |

| category | ms | share |
|---|---|---|
| matmul MoE experts (MXFP4) | 6457 | 46.4% |
| matmul (quantized, other) | 5039 | 36.2% |
| flash attention | 1140 | 8.2% |
| activation quantize | 244 | 1.8% |
| router / softmax / top-k | 223 | 1.6% |
| elementwise (add/mul/glu/...) | 222 | 1.6% |
| norm | 163 | 1.2% |
| matmul (f16/f32 / cuBLAS) | 103 | 0.7% |
| rope | 100 | 0.7% |
| KV cache write / copy | 94 | 0.7% |
| other | 68 | 0.5% |
| gather / get_rows | 60 | 0.4% |
