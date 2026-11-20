"""Lightweight hierarchical span tracer.

Each span records:
  - wall time (perf_counter_ns)
  - process CPU time (all threads of *this* process, so ONNX/numpy worker
    threads are included; cpu/wall > 1 means intra-op parallelism)
  - syscall-level I/O (rchar/wchar) and block-device I/O (read_bytes/write_bytes)
  - minor/major page faults
  - arbitrary attributes (token counts, batch sizes, collection names, ...)

Spans nest per-thread; `self_ms` (wall minus direct children) is computed at
analysis time and approximates "glue" overhead of the instrumented layer.
"""
from __future__ import annotations

import contextlib
import functools
import json
import os
import resource
import threading
import time
from typing import Any, Callable

import psutil

_PROC = psutil.Process(os.getpid())


def _io() -> tuple[int, int, int, int]:
    try:
        c = _PROC.io_counters()
        return c.read_chars, c.write_chars, c.read_bytes, c.write_bytes
    except Exception:  # pragma: no cover - not all kernels expose this
        return 0, 0, 0, 0


class Tracer:
    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []
        self._tls = threading.local()
        self._next_id = 0
        self._lock = threading.Lock()
        self.enabled = True
        self.context: dict[str, Any] = {}  # attached to every span (e.g. turn id)

    # ------------------------------------------------------------------ core
    def _stack(self) -> list[int]:
        st = getattr(self._tls, "stack", None)
        if st is None:
            st = self._tls.stack = []
        return st

    @contextlib.contextmanager
    def span(self, name: str, **attrs: Any):
        if not self.enabled:
            yield attrs
            return
        with self._lock:
            sid = self._next_id
            self._next_id += 1
        st = self._stack()
        parent = st[-1] if st else None
        st.append(sid)
        ru0 = resource.getrusage(resource.RUSAGE_SELF)
        io0 = _io()
        cpu0 = time.process_time_ns()
        t0 = time.perf_counter_ns()
        err = None
        try:
            yield attrs  # callee may add attributes
        except BaseException as e:  # record and re-raise
            err = repr(e)[:200]
            raise
        finally:
            t1 = time.perf_counter_ns()
            cpu1 = time.process_time_ns()
            io1 = _io()
            ru1 = resource.getrusage(resource.RUSAGE_SELF)
            st.pop()
            rec = {
                "id": sid,
                "parent": parent,
                "name": name,
                "thread": threading.get_ident(),
                "t0_ns": t0,
                "wall_ms": (t1 - t0) / 1e6,
                "cpu_ms": (cpu1 - cpu0) / 1e6,
                "rchar": io1[0] - io0[0],
                "wchar": io1[1] - io0[1],
                "read_bytes": io1[2] - io0[2],
                "write_bytes": io1[3] - io0[3],
                "minflt": ru1.ru_minflt - ru0.ru_minflt,
                "majflt": ru1.ru_majflt - ru0.ru_majflt,
                **self.context,
                **attrs,
            }
            if err:
                rec["error"] = err
            with self._lock:
                self.spans.append(rec)

    def wrap(self, obj: Any, attr: str, name: str | None = None,
             attrs_fn: Callable[..., dict] | None = None,
             post_fn: Callable[[Any, dict], None] | None = None,
             materialize: bool = False) -> None:
        """Monkeypatch obj.attr with a traced version (idempotent)."""
        orig = getattr(obj, attr)
        if getattr(orig, "__memprof_wrapped__", False):
            return
        span_name = name or f"{getattr(obj, '__name__', type(obj).__name__)}.{attr}"
        tracer = self

        @functools.wraps(orig)
        def wrapped(*a, **k):
            extra = {}
            if attrs_fn is not None:
                try:
                    extra = attrs_fn(*a, **k) or {}
                except Exception:
                    extra = {}
            with tracer.span(span_name, **extra) as sattrs:
                out = orig(*a, **k)
                if materialize:  # force lazy generators to run inside the span
                    out = list(out)
                if post_fn is not None:
                    try:
                        post_fn(out, sattrs)
                    except Exception:
                        pass
                return out

        wrapped.__memprof_wrapped__ = True  # type: ignore[attr-defined]
        setattr(obj, attr, wrapped)

    # ------------------------------------------------------------------ io
    def dump(self, path: str) -> None:
        with open(path, "w") as f:
            for s in self.spans:
                f.write(json.dumps(s, default=str) + "\n")

    def reset(self) -> None:
        with self._lock:
            self.spans.clear()


TRACER = Tracer()


def measure_overhead(n: int = 20000) -> float:
    """Return per-span tracer overhead in microseconds (empty span)."""
    t = Tracer()
    t0 = time.perf_counter_ns()
    for _ in range(n):
        with t.span("x"):
            pass
    return (time.perf_counter_ns() - t0) / n / 1e3
