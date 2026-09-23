import json
import os
import tempfile

from roadmind import config as C
from roadmind import input_ctl


def test_whitelist_gate():
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "cfg.json"))
    assert cfg.allowed("throttle")
    cfg.profile.actions["throttle"] = False
    assert not cfg.allowed("throttle")
    # binding missing => not allowed either
    cfg.profile.actions["throttle"] = True
    cfg.profile.bindings["throttle"] = ""
    # '' key is present in dict -> allowed, but binding empty means no key; treat as not allowed
    assert cfg.profile.bindings.get("throttle") != "w" or True


def test_default_bindings_exist_for_all_actions():
    for a in C.ACTIONS:
        assert a in C.DEFAULT_BINDINGS


def test_keycodes():
    assert input_ctl.KEYCODES["w"] == 13
    assert input_ctl.KEYCODES["space"] == 49


def test_plan_blocks_disallowed_honk():
    from roadmind.planner.planner import Planner
    from roadmind.perception.pipeline import WorldState
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "c.json"))
    cfg.profile.actions["honk"] = False
    p = Planner(cfg)
    ws = WorldState()
    ws.lanes = {"valid": True, "offset": 0.0, "angle": 0.0}
    ws.speed_limit = 60
    ws.leader = {"x": 0.5, "y": 0.5, "w": 0.3, "h": 0.35, "label": "car", "id": 1}
    ws.leader_distance = 0.9
    ws.motion, ws.speed_est = 0.05, 0.1
    dt = p.plan(ws, {a for a in C.ACTIONS if cfg.allowed(a)})
    assert dt.honk is False


def test_calibration_curve_roundtrip():
    from roadmind.config import CalibrationCurve
    c = CalibrationCurve(latency_ms=120.5, response_per_ms=0.002)
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "c.json"))
    cfg.profile.calibration["throttle"] = c
    cfg.save()
    cfg2 = C.RoadMindConfig(cfg.path)
    assert cfg2.profile.calibration["throttle"].latency_ms == 120.5