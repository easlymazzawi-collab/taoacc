"""
core_runtime.py — hạ tầng dùng chung
=====================================
Giải quyết 3 nguyên nhân gốc khiến tool đơ + setting reset:

1. LogBus  (fix đơ #1):
   Bản gốc gọi parent.after(0, write) cho TỪNG dòng log → khi batch 1000+
   thao tác → main loop tk nghẹn → UI đơ.
   Bản mới: log dồn vào queue, 1 timer flush cả batch lên widget.

2. SharedTaskRunner  (fix đơ #2):
   Bản gốc: mỗi AccountRow tạo 1 loop, mỗi _run_in_bg tạo loop mới →
   30+ event loop → GIL contention.
   Bản mới: 1 event loop nền duy nhất + cancel task theo id.

3. ConfigStore  (fix setting reset):
   Auto save/load JSON, bind 2-way với Entry/StringVar.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Optional


# ────────────────────────────────────────────────────────────────────
class LogBus:
    """Gom log thành batch, flush mỗi FLUSH_MS. Thread-safe."""

    FLUSH_MS = 100
    MAX_LINES = 5_000
    DROP_BATCH = 1_000

    COLOR = {
        "ok":         "#00cc66",
        "error":      "#ff5555",
        "fresh":      "#ffaa44",
        "no_perm":    "#ff5555",
        "not_member": "#ff8844",
        "privacy":    "#ff8844",
        "invalid":    "#ff8844",
        "skip":       "#888888",
        "info":       "#88ccff",
    }

    def __init__(self, tk_root):
        self.root = tk_root
        self._q: "queue.Queue" = queue.Queue()
        self._widget = None
        self._status_setter: Optional[Callable[[str, str], None]] = None
        self._line_count = 0
        self._closed = False
        self._tags_setup = False
        self._filter: Optional[set] = None
        self._buffer_for_export: deque = deque(maxlen=20_000)
        self._schedule_flush()

    def attach_widget(self, textbox_widget):
        self._widget = textbox_widget
        self._tags_setup = False

    def attach_status_setter(self, fn):
        self._status_setter = fn

    def set_filter(self, levels):
        self._filter = levels

    def write(self, level: str, msg: str):
        if self._closed: return
        level = level or "info"
        self._q.put((level, msg))
        self._buffer_for_export.append((time.time(), level, msg))
        if self._status_setter and msg.strip():
            short = msg.strip().replace("\n", " ")
            if len(short) > 120:
                short = short[:117] + "..."
            color = self.COLOR.get(level, "#88ccff")
            try: self._status_setter(short, color)
            except Exception: pass

    def __call__(self, level: str, msg: str):
        self.write(level, msg)

    def clear(self):
        self._q.put(("__CLEAR__", ""))

    def export_lines(self):
        return [f"{time.strftime('%H:%M:%S', time.localtime(t))}\t{lv}\t{m}"
                for t, lv, m in self._buffer_for_export]

    def stop(self):
        self._closed = True

    def _schedule_flush(self):
        if self._closed: return
        try:
            self.root.after(self.FLUSH_MS, self._flush)
        except Exception: pass

    def _setup_tags(self):
        if self._tags_setup or self._widget is None: return
        try:
            for level, color in self.COLOR.items():
                self._widget.tag_config(level, foreground=color)
            self._tags_setup = True
        except Exception: pass

    def _flush(self):
        try:
            if self._widget is None: return
            self._setup_tags()
            batch = []
            while True:
                try: item = self._q.get_nowait()
                except queue.Empty: break
                if item[0] == "__CLEAR__":
                    try: self._widget.delete("0.0", "end")
                    except Exception: pass
                    self._line_count = 0
                    batch.clear()
                    continue
                batch.append(item)

            if batch:
                try:
                    for level, msg in batch:
                        if self._filter is not None and level not in self._filter:
                            continue
                        line = msg if msg.endswith("\n") else msg + "\n"
                        self._widget.insert("end", line, level)
                        self._line_count += 1
                    self._widget.see("end")
                    if self._line_count > self.MAX_LINES:
                        drop = self.DROP_BATCH
                        self._widget.delete("0.0", f"{drop + 1}.0")
                        self._line_count -= drop
                except Exception: pass
        finally:
            self._schedule_flush()


# ────────────────────────────────────────────────────────────────────
class SharedTaskRunner:
    """1 event loop nền duy nhất cho cả app."""

    def __init__(self):
        self._loop = None
        self._thread = None
        self._tasks = {}
        self._counter = 0
        self._lock = threading.Lock()

    def start(self):
        if self._loop is not None: return self
        self._loop = asyncio.new_event_loop()
        ev = threading.Event()

        def runner():
            asyncio.set_event_loop(self._loop)
            ev.set()
            try: self._loop.run_forever()
            finally:
                try: self._loop.close()
                except Exception: pass

        self._thread = threading.Thread(target=runner, daemon=True, name="TaskRunner")
        self._thread.start()
        ev.wait(2.0)
        return self

    @property
    def loop(self):
        return self._loop

    def submit(self, name, coro, on_done=None, on_error=None):
        if self._loop is None:
            raise RuntimeError("Runner chưa start()")
        with self._lock:
            self._counter += 1
            tid = f"{name}#{self._counter}"

        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        self._tasks[tid] = fut

        def watcher():
            try:
                result = fut.result()
                if on_done:
                    try: on_done(result)
                    except Exception: pass
            except asyncio.CancelledError:
                if on_error:
                    try: on_error(asyncio.CancelledError("Đã hủy"))
                    except Exception: pass
            except BaseException as e:
                if on_error:
                    try: on_error(e)
                    except Exception: pass
            finally:
                self._tasks.pop(tid, None)

        threading.Thread(target=watcher, daemon=True, name=f"w-{tid}").start()
        return tid

    def cancel(self, tid):
        fut = self._tasks.get(tid)
        return bool(fut and fut.cancel())

    def cancel_all(self):
        n = 0
        for tid, fut in list(self._tasks.items()):
            if fut.cancel(): n += 1
        return n

    def running_count(self):
        return len(self._tasks)

    def running_tasks(self):
        return list(self._tasks.keys())

    def shutdown(self):
        if self._loop is None: return
        self.cancel_all()
        try: self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception: pass
        if self._thread:
            self._thread.join(timeout=2)
        self._loop = None


# ────────────────────────────────────────────────────────────────────
class ConfigStore:
    """Auto-save/load JSON config. Debounce ghi đĩa."""

    SAVE_DELAY_MS = 800

    def __init__(self, path, tk_root=None):
        self.path = Path(path)
        self._data = {}
        self._lock = threading.Lock()
        self._tk_root = tk_root
        self._save_pending = False
        self.load()

    def load(self):
        if not self.path.exists(): return
        try:
            with open(self.path, encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def save(self):
        with self._lock:
            try:
                tmp = self.path.with_suffix(self.path.suffix + ".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                tmp.replace(self.path)
            except Exception:
                pass
            self._save_pending = False

    def _schedule_save(self):
        if self._tk_root is None:
            self.save(); return
        if self._save_pending: return
        self._save_pending = True
        try:
            self._tk_root.after(self.SAVE_DELAY_MS, self.save)
        except Exception:
            self.save()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        with self._lock:
            if self._data.get(key) != value:
                self._data[key] = value
        self._schedule_save()

    def bind_var(self, tk_var, key, default=None):
        cur = self.get(key, default)
        if cur is not None:
            try: tk_var.set(cur)
            except Exception: pass
        def _on_change(*_):
            try: v = tk_var.get()
            except Exception: return
            self.set(key, v)
        try: tk_var.trace_add("write", _on_change)
        except Exception: pass

    def bind_entry(self, entry_widget, key, default=""):
        cur = self.get(key, default)
        if cur:
            try:
                entry_widget.delete(0, "end")
                entry_widget.insert(0, str(cur))
            except Exception: pass
        def _on_change(_e=None):
            try: self.set(key, entry_widget.get())
            except Exception: pass
        try:
            entry_widget.bind("<KeyRelease>", _on_change)
            entry_widget.bind("<FocusOut>", _on_change)
        except Exception: pass

    def bind_textbox(self, tb, key, default=""):
        cur = self.get(key, default)
        if cur:
            try:
                tb.delete("0.0", "end")
                tb.insert("0.0", str(cur))
            except Exception: pass
        def _on_change(_e=None):
            try:
                content = tb.get("0.0", "end").rstrip("\n")
                self.set(key, content)
            except Exception: pass
        try: tb.bind("<FocusOut>", _on_change)
        except Exception: pass


# ────────────────────────────────────────────────────────────────────
class AsyncBridge:
    """Wrapper gọn cho UI handler."""

    def __init__(self, runner, log_bus, on_status=None):
        self.runner = runner
        self.log = log_bus
        self.on_status = on_status or (lambda *_a, **_k: None)

    def run(self, name, coro, busy_msg=None, done_msg=None, on_done=None):
        if busy_msg:
            self.on_status(busy_msg, "#ffcc00")

        def _done(result):
            if done_msg: self.on_status(done_msg, "#00cc66")
            if on_done:
                try: on_done(result)
                except Exception: pass

        def _err(e):
            import traceback
            if isinstance(e, asyncio.CancelledError):
                self.log.write("info", "⏹ Task đã hủy")
                self.on_status("⏹ Đã hủy", "#ffaa44")
            else:
                self.log.write("error", f"💥 LỖI: {type(e).__name__}: {e}")
                self.log.write("error", traceback.format_exc())
                self.on_status(f"❌ {str(e)[:80]}", "#ff5555")

        return self.runner.submit(name, coro, on_done=_done, on_error=_err)
