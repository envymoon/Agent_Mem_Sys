"""System-agnostic OpenAI-compatible logging proxy.

Every memory system under test (mem0, Graphiti, Letta, ...) is pointed at this proxy instead of the
inference server, so all LLM / embedding traffic is measured the same way, whether the system runs
in-process (library) or as its own server (Letta).

Per request it logs (jsonl, one line per call):
  t0_ns / t_first_ns / t1_ns   perf_counter_ns (CLOCK_MONOTONIC: comparable across processes on Linux)
  ttft_ms, decode_ms           non-streamed chat requests are converted to streamed upstream and
                               reassembled, so TTFT (queue + prefill) and decode are measured for
                               every system without touching its code
  prompt_tokens, completion_tokens, cached_tokens (vLLM --enable-prompt-tokens-details / llama.cpp)
  llama.cpp 'timings' block when present (prompt_ms, predicted_ms, cache_n)
  reasoning models: t_answer_ns (first answer token), reasoning_ms / answer_ms (decode split),
                    reasoning_chunks / answer_chunks (= tokens: one token per streamed chunk),
                    reasoning_tokens when the server reports completion_tokens_details
  request shape: n_messages, prompt_chars, tools, response_format, max_tokens, client tag

Rewrites: `model` -> served model name (systems ship with gpt-4o-mini etc. as defaults);
optionally disables Qwen3 thinking (chat_template_kwargs.enable_thinking=false).

usage:
  python -m memprof.llm_proxy --port 8100 --chat http://127.0.0.1:8000 --embed http://127.0.0.1:8001 \
      --chat-model Qwen/Qwen3-8B --embed-model Qwen/Qwen3-Embedding-0.6B --log results/x/llm_calls.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

from aiohttp import ClientSession, ClientTimeout, TCPConnector, web

A = None  # parsed args


def now() -> int:
    return time.perf_counter_ns()


class Log:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.f = open(path, "a", buffering=1)
        self.n = 0

    def write(self, rec: dict) -> None:
        self.n += 1
        rec["seq"] = self.n
        self.f.write(json.dumps(rec) + "\n")

    def reopen(self, path: str) -> None:
        self.f.close()
        self.__init__(path)


def _req_shape(body: dict) -> dict:
    msgs = body.get("messages") or []
    chars = 0
    for m in msgs:
        c = m.get("content")
        if isinstance(c, str):
            chars += len(c)
        elif isinstance(c, list):
            chars += sum(len(p.get("text", "")) for p in c if isinstance(p, dict))
    rf = body.get("response_format") or {}
    return {"n_messages": len(msgs), "prompt_chars": chars, "n_tools": len(body.get("tools") or []),
            "response_format": rf.get("type") if isinstance(rf, dict) else None,
            "max_tokens": body.get("max_tokens") or body.get("max_completion_tokens"),
            "req_model": body.get("model"), "stream_req": bool(body.get("stream"))}


def _usage(rec: dict, usage: dict | None) -> None:
    if not usage:
        return
    rec["prompt_tokens"] = usage.get("prompt_tokens")
    rec["completion_tokens"] = usage.get("completion_tokens")
    d = usage.get("prompt_tokens_details") or {}
    if d.get("cached_tokens") is not None:
        rec["cached_tokens"] = d["cached_tokens"]
    r = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if r is not None:  # server-side count where provided (vLLM, OpenAI); else reasoning_chunks
        rec["reasoning_tokens"] = r


def _timings(rec: dict, t: dict | None) -> None:
    if t:  # llama.cpp server
        rec["llama_timings"] = {k: t.get(k) for k in ("prompt_n", "prompt_ms", "predicted_n", "predicted_ms", "cache_n")}
        if rec.get("cached_tokens") is None and t.get("cache_n") is not None:
            rec["cached_tokens"] = t["cache_n"]


def _rewrite(body: dict, kind: str) -> dict:
    if kind == "chat":
        if A.chat_model:
            body["model"] = A.chat_model
        if A.no_think:
            ck = body.setdefault("chat_template_kwargs", {})
            ck.setdefault("enable_thinking", False)
        if A.chat_kwargs:  # e.g. gpt-oss {"reasoning_effort": "low"}
            ck = body.setdefault("chat_template_kwargs", {})
            for k, v in A.chat_kwargs.items():
                ck.setdefault(k, v)
        for k in A.drop_params:
            body.pop(k, None)
        body.update(A.inject)  # e.g. {"cache_prompt": false} for the llama.cpp prefix-cache ablation
    elif kind == "embed":
        if A.embed_model:
            body["model"] = A.embed_model
        body.pop("dimensions", None)  # truncation (if any) is done here, see --embed-dims
    return body


def _dump(rec: dict, req_msgs, resp_msg) -> None:
    """--dump-bodies FILE: full request messages + response message per chat call (debugging extraction
    quality; off by default because it holds the conversation text)."""
    if A.dump_bodies and req_msgs is not None:
        with open(A.dump_bodies, "a") as f:
            f.write(json.dumps({"seq": rec.get("seq"), "client": rec.get("client"), "messages": req_msgs,
                                "response": resp_msg, "finish": rec.get("finish")}) + "\n")


async def handle_chat(request: web.Request) -> web.StreamResponse:
    body = await request.json()
    req_msgs = body.get("messages") if A.dump_bodies else None
    rec = {"kind": "chat", "client": request.headers.get("X-Memprof-Client", ""),
           "ua": request.headers.get("User-Agent", "")[:60], **_req_shape(body)}
    body = _rewrite(body, "chat")
    url = A.chat.rstrip("/") + "/v1/chat/completions"
    hdr = {"Content-Type": "application/json", "Authorization": "Bearer sk-local"}
    client_stream = bool(body.get("stream"))
    convert = (not client_stream) and A.stream_convert and (body.get("n") in (None, 1))
    t0 = now()
    rec["t0_ns"] = t0
    sess: ClientSession = request.app["sess"]
    if not client_stream and not convert:
        async with sess.post(url, json=body, headers=hdr) as r:
            data = await r.json(content_type=None)
            rec["t1_ns"] = now()
            rec["status"] = r.status
        _usage(rec, data.get("usage"))
        _timings(rec, data.get("timings"))
        if data.get("metrics"):
            rec["vllm_metrics"] = data["metrics"]
        rec["wall_ms"] = (rec["t1_ns"] - t0) / 1e6
        request.app["log"].write(rec)
        _dump(rec, req_msgs, ((data.get("choices") or [{}])[0]).get("message"))
        return web.json_response(data, status=r.status)

    body["stream"] = True
    so = body.setdefault("stream_options", {})
    so["include_usage"] = True
    first = None
    t_ans = None           # first answer (content / tool-call) token; before it: reasoning tokens (gpt-oss, qwen3 ...)
    n_rs = n_ans = 0       # streamed chunks per phase (llama.cpp / vLLM stream one token per chunk)
    content, reasoning, tool_calls = [], [], {}
    meta, finish, usage, timings, vmetrics = {}, None, None, None, None
    out = None
    if client_stream:
        out = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await out.prepare(request)
    async with sess.post(url, json=body, headers=hdr) as r:
        rec["status"] = r.status
        if r.status != 200:
            txt = await r.text()
            rec["t1_ns"] = now()
            rec["wall_ms"] = (rec["t1_ns"] - t0) / 1e6
            rec["error"] = txt[:500]
            request.app["log"].write(rec)
            if out is not None:
                await out.write(f"data: {txt}\n\n".encode())
                return out
            return web.Response(text=txt, status=r.status, content_type="application/json")
        buf = b""
        async for chunk in r.content.iter_any():
            if out is not None:
                await out.write(chunk)
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                payload = line[5:].strip()
                if payload == b"[DONE]":
                    continue
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if not meta:
                    meta = {"id": ev.get("id"), "created": ev.get("created"), "model": ev.get("model")}
                if ev.get("usage"):
                    usage = ev["usage"]
                if ev.get("timings"):
                    timings = ev["timings"]
                if ev.get("metrics"):  # vLLM --enable-per-request-metrics
                    vmetrics = ev["metrics"]
                for ch in ev.get("choices") or []:
                    d = ch.get("delta") or {}
                    got = ans = False
                    if d.get("content"):
                        content.append(d["content"]); got = ans = True
                    if d.get("reasoning_content"):
                        reasoning.append(d["reasoning_content"]); got = True; n_rs += 1
                    for tc in d.get("tool_calls") or []:
                        got = ans = True
                        slot = tool_calls.setdefault(tc.get("index", 0), {"id": None, "type": "function",
                                                                          "function": {"name": "", "arguments": ""}})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        f = tc.get("function") or {}
                        if f.get("name"):
                            slot["function"]["name"] += f["name"]
                        if f.get("arguments"):
                            slot["function"]["arguments"] += f["arguments"]
                    if got and first is None:
                        first = now()
                    if ans:
                        n_ans += 1
                        if t_ans is None:
                            t_ans = now()
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
    t1 = now()
    rec.update({"t1_ns": t1, "t_first_ns": first, "wall_ms": (t1 - t0) / 1e6,
                "ttft_ms": ((first or t1) - t0) / 1e6, "decode_ms": (t1 - (first or t1)) / 1e6,
                "finish": finish, "converted": convert})
    # split of the decode phase: reasoning [first, t_ans) vs answer [t_ans, t1); zeros = no reasoning
    rec.update({"t_answer_ns": t_ans, "reasoning_chunks": n_rs, "answer_chunks": n_ans,
                "reasoning_chars": sum(map(len, reasoning)), "answer_chars": sum(map(len, content)),
                "reasoning_ms": ((t_ans or t1) - first) / 1e6 if first and n_rs else 0.0,
                "answer_ms": (t1 - (t_ans or t1)) / 1e6 if n_rs else (t1 - (first or t1)) / 1e6})
    _usage(rec, usage)
    _timings(rec, timings)
    if vmetrics:
        rec["vllm_metrics"] = {k: vmetrics.get(k) for k in ("queue_time_ms", "time_to_first_token_ms",
                                                            "generation_time_ms", "mean_itl_ms")}
    request.app["log"].write(rec)
    if out is not None:
        return out
    msg = {"role": "assistant", "content": "".join(content) if content or not tool_calls else None}
    if reasoning:
        msg["reasoning_content"] = "".join(reasoning)
    if tool_calls:
        msg["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
    _dump(rec, req_msgs, msg)
    resp = {**meta, "object": "chat.completion",
            "choices": [{"index": 0, "message": msg, "finish_reason": finish, "logprobs": None}],
            "usage": usage}
    return web.json_response(resp)


async def handle_embed(request: web.Request) -> web.Response:
    body = await request.json()
    inp = body.get("input")
    n = len(inp) if isinstance(inp, list) and inp and not isinstance(inp[0], int) else 1
    chars = len(inp) if isinstance(inp, str) else sum(len(x) for x in inp if isinstance(x, str)) if isinstance(inp, list) else 0
    rec = {"kind": "embed", "client": request.headers.get("X-Memprof-Client", ""), "n_inputs": n,
           "input_chars": chars, "req_model": body.get("model")}
    body = _rewrite(body, "embed")
    url = A.embed.rstrip("/") + "/v1/embeddings"
    t0 = now()
    async with request.app["sess"].post(url, json=body, headers={"Authorization": "Bearer sk-local"}) as r:
        data = await r.json(content_type=None)
        status = r.status
    t1 = now()
    rec.update({"t0_ns": t0, "t1_ns": t1, "wall_ms": (t1 - t0) / 1e6, "status": status})
    _usage(rec, data.get("usage") if isinstance(data, dict) else None)
    request.app["log"].write(rec)
    if isinstance(data, dict) and A.embed_dims and "data" in data:  # Matryoshka truncation if asked
        for d in data["data"]:
            d["embedding"] = d["embedding"][: A.embed_dims]
    return web.json_response(data, status=status)


async def handle_passthrough(request: web.Request) -> web.Response:
    base = A.embed if "embed" in request.path else A.chat
    url = base.rstrip("/") + request.path_qs
    data = await request.read()
    async with request.app["sess"].request(request.method, url, data=data,
                                           headers={"Content-Type": request.headers.get("Content-Type", "application/json")}) as r:
        return web.Response(body=await r.read(), status=r.status, content_type=r.content_type)


async def handle_models(request: web.Request) -> web.Response:
    """Upstream model list, plus `max_model_len` (Letta's vLLM provider needs it; llama.cpp omits it)."""
    async with request.app["sess"].get(A.chat.rstrip("/") + "/v1/models") as r:
        data = await r.json(content_type=None)
    for m in data.get("data", []):
        m.setdefault("max_model_len", A.ctx)
    return web.json_response(data)


async def handle_ctl(request: web.Request) -> web.Response:
    """POST /memprof/log {"path": ...} switches the log file (one proxy for many runs)."""
    body = await request.json()
    request.app["log"].reopen(body["path"])
    return web.json_response({"ok": True, "path": body["path"]})


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


def main() -> None:
    global A
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--chat", default="http://127.0.0.1:8000")
    ap.add_argument("--embed", default="http://127.0.0.1:8001")
    ap.add_argument("--chat-model", default="")
    ap.add_argument("--embed-model", default="")
    ap.add_argument("--embed-dims", type=int, default=0)
    ap.add_argument("--ctx", type=int, default=32768, help="context length advertised in /v1/models")
    ap.add_argument("--no-think", action="store_true")
    ap.add_argument("--no-stream-convert", dest="stream_convert", action="store_false")
    ap.add_argument("--drop-params", default="", help="comma list of request keys to drop")
    ap.add_argument("--chat-kwargs", default="{}", help="JSON added to chat_template_kwargs of every chat request")
    ap.add_argument("--inject", default="{}", help="JSON merged into every chat request body")
    ap.add_argument("--log", default="results/llm_calls.jsonl")
    ap.add_argument("--dump-bodies", default="", help="append full chat request/response bodies to this jsonl")
    A = ap.parse_args()
    A.inject = json.loads(A.inject)
    A.chat_kwargs = json.loads(A.chat_kwargs)
    A.drop_params = [x for x in A.drop_params.split(",") if x]

    async def on_start(app):
        app["sess"] = ClientSession(timeout=ClientTimeout(total=3600), connector=TCPConnector(limit=256))

    async def on_stop(app):
        await app["sess"].close()

    app = web.Application(client_max_size=256 * 1024 ** 2)
    app["log"] = Log(A.log)
    app.on_startup.append(on_start)
    app.on_cleanup.append(on_stop)
    app.router.add_post("/v1/chat/completions", handle_chat)
    app.router.add_post("/chat/completions", handle_chat)
    app.router.add_post("/v1/embeddings", handle_embed)
    app.router.add_post("/embeddings", handle_embed)
    app.router.add_get("/v1/models", handle_models)
    app.router.add_post("/memprof/log", handle_ctl)
    app.router.add_get("/memprof/health", health)
    app.router.add_route("*", "/{tail:.*}", handle_passthrough)
    web.run_app(app, host="127.0.0.1", port=A.port, access_log=None, print=lambda *_: None)


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    main()
