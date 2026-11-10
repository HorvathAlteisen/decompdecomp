"""What every claim's brief reads is read by one thread at a time: when many helpers asked at once before it was
ready, each read all of it again (39 of 70 helpers on a DS game read its 557 objects for the twins, 46 s apiece)."""

import threading
import time
from types import SimpleNamespace

from decompnet.app.forkengine import ForkEngine
from decompnet.app.twins import Twins

HELPERS = 8


def _all_at_once(ask):
    """Calls `ask` from HELPERS threads that start together; what they got back."""
    start = threading.Barrier(HELPERS)
    got = []

    def helper():
        start.wait()
        got.append(ask())

    threads = [threading.Thread(target=helper) for _ in range(HELPERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return got


def test_helpers_that_ask_for_a_forks_prints_at_once_read_them_once():
    twins = Twins(SimpleNamespace(fork_slug=lambda slug: slug))
    reads = []

    def read(proj):
        reads.append(1)
        time.sleep(0.3)  # reading the objects takes time: the others ask meanwhile
        return {1: "print"}

    twins._fork_prints = read
    got = _all_at_once(lambda: twins.prints({"id": 1, "slug": "game"}))
    assert got == [{1: "print"}] * HELPERS
    assert len(reads) == 1


def test_helpers_that_ask_for_the_data_index_at_once_read_the_objects_once(tmp_path):
    forks = ForkEngine(SimpleNamespace())
    reads = []

    def units():
        reads.append(1)
        time.sleep(0.3)
        return []

    fp = SimpleNamespace(root=tmp_path, units=units)
    got = _all_at_once(lambda: forks._data_index({"id": 1}, fp))
    assert got == [{}] * HELPERS
    assert len(reads) == 1
    (tmp_path / "objdiff.json").write_text("{}")  # a new objdiff.json: read again
    assert forks._data_index({"id": 1}, fp) == {} and len(reads) == 2
