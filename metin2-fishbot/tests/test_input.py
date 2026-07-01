import threading
import time

from metin2fishbot.core.input_controller import InputController


def test_dry_run_has_no_backend():
    ic = InputController(dry_run=True)
    assert ic.dry_run is True
    assert ic._backend is None
    # actions are safe no-ops in dry-run
    ic.press_key("1")
    ic.click(10, 20)
    ic.type_text("hello")


def test_radius_offset_within_bounds():
    ic = InputController(dry_run=True, click_radius=3)
    for _ in range(50):
        x, y = ic._radius_offset(100, 100)
        assert 97 <= x <= 103
        assert 97 <= y <= 103


def test_lock_serializes_actions():
    """Two threads hammering the controller must never interleave a critical
    section (the lock is an RLock shared by all public actions)."""
    ic = InputController(dry_run=True)
    order = []
    active = {"count": 0}
    fail = {"hit": False}

    def action(tag):
        with ic.lock:
            active["count"] += 1
            if active["count"] > 1:
                fail["hit"] = True
            time.sleep(0.001)
            active["count"] -= 1
            order.append(tag)

    threads = [threading.Thread(target=action, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not fail["hit"]       # never two inside the lock at once
    assert len(order) == 20


def test_jitter_zero_returns_base():
    ic = InputController(dry_run=True, delay_jitter=0)
    assert ic._jitter(0.5) == 0.5
