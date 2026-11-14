"""The background workers machine drafts (drafts.py) and the permuter (permute.py) share, for every project.

One pool, so "up to four workers" holds for the app as a whole: each part with a pool of its own made eight threads
on a big computer, beside the agents' compiles. Each worker lowers its own CPU priority as it starts (on Linux a
thread's own, inherited by what it runs; on macOS, the thread's QoS), so the app and
the agents come first.
"""

from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

RESERVED_CORES = 2  # left to the app itself and the agents' compiles
# Past four, the judge's own Python work (about 5 ms of a variant's 16, under the interpreter's one lock) is the
# limit, not the cores, and the app itself waits for that lock. Demo ROM, 12 cores: 1 worker judged 80 variants a
# second, 2 129, 4 172, 8 193; a GUI request took 0.1 ms alone, 6 ms beside 4 workers, 31 ms beside 8.
MAX_WORKERS = 4
WORKERS = max(1, min(MAX_WORKERS, (os.cpu_count() or 1) - RESERVED_CORES))
NICE = 10  # how much lower the workers' CPU priority is

# How long a thread keeps the interpreter's one lock while another waits for it (Python's own: 5 ms). A request of
# the window gives the lock away at each file it looks at and each database statement, and waited that long to get
# it back, each time, while any thread of the app computed in Python: a DS project's live poll (40 ms alone) took
# 4.1 s beside one such thread and 43 s beside four, so the project page didn't load. At 0.5 ms: 0.5 s and 4.5 s.
# Threads that compute take as long as before when there are one or two, and 5% longer when there are four or eight.
INTERPRETER_TURN_SECONDS = 0.0005

_pool: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def _lower_priority() -> None:
    """Lower only this worker, without lowering the GUI or the agent threads beside it."""
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.GetCurrentThread.restype = ctypes.c_void_p
        kernel.SetThreadPriority.argtypes = (ctypes.c_void_p, ctypes.c_int)
        kernel.SetThreadPriority(kernel.GetCurrentThread(), -1)  # THREAD_PRIORITY_BELOW_NORMAL
    elif sys.platform == "darwin":
        import ctypes

        # Darwin's nice value belongs to the process, so os.nice would slow the GUI too.
        # Set this worker's QoS instead. Utility threads still let the interactive window run first.
        system = ctypes.CDLL(None)
        system.pthread_set_qos_class_self_np.argtypes = (ctypes.c_uint, ctypes.c_int)
        system.pthread_set_qos_class_self_np(0x11, 0)  # QOS_CLASS_UTILITY
    else:
        os.nice(NICE)


def take_short_turns() -> None:
    """The app's threads take the interpreter in short turns (INTERPRETER_TURN_SECONDS), for the whole process: the
    window's requests and the agents' tool calls don't wait behind the threads that compute. Called as the app
    starts (cli.run).

    Not on Windows, which keeps Python's own turns: Python 3.12 waits for the lock there in whole milliseconds
    (condvar.h: `us/1000`), so a turn under 1 ms is a wait of none, and the threads that wait ask for the lock again
    and again without a pause. No turn was measured on Windows yet."""
    if os.name == "nt":
        return
    sys.setswitchinterval(INTERPRETER_TURN_SECONDS)


def pool() -> ThreadPoolExecutor:
    """The shared workers, started the first time something needs them."""
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(WORKERS, thread_name_prefix="background-worker", initializer=_lower_priority)
        return _pool
