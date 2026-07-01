from metin2fishbot.safety.guards import SafetyGuard


def test_action_cap_stops():
    guard = SafetyGuard(max_actions=3)
    guard.start()
    assert guard.should_continue()
    guard.record_action(3)
    assert not guard.should_continue()
    guard.stop()


def test_runtime_cap_stops(monkeypatch):
    import metin2fishbot.safety.guards as guards_mod

    t = {"now": 1000.0}
    monkeypatch.setattr(guards_mod.time, "time", lambda: t["now"])
    guard = SafetyGuard(max_runtime_minutes=1)  # 60s
    guard.start()
    assert guard.should_continue()
    t["now"] += 61
    assert not guard.should_continue()


def test_request_stop_flags_stopped():
    guard = SafetyGuard()
    guard.start()
    assert guard.should_continue()
    guard.request_stop()
    assert guard.stopped
    assert not guard.should_continue()


def test_maybe_break_taken_with_injected_clock(monkeypatch):
    import metin2fishbot.safety.guards as guards_mod

    t = {"now": 0.0}
    monkeypatch.setattr(guards_mod.time, "time", lambda: t["now"])
    slept = []
    guard = SafetyGuard(break_every_minutes=1, break_duration_seconds=2)
    guard.start()                 # sets _last_break_ts = 0
    assert guard.maybe_break(sleeper=slept.append) is False  # not due yet
    t["now"] = 61                 # past the 60s interval
    assert guard.maybe_break(sleeper=slept.append) is True
    assert sum(slept) > 0         # it actually "slept" through the break


def test_no_break_when_disabled():
    guard = SafetyGuard(break_every_minutes=0)
    guard.start()
    assert guard.maybe_break(sleeper=lambda s: None) is False
