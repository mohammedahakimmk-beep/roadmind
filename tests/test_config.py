import json
import os
import tempfile

from roadmind import config as C
from roadmind import input_ctl
from roadmind import sys_utils


def test_whitelist_gate():
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "cfg.json"))
    assert cfg.allowed("throttle")
    cfg.profile.actions["throttle"] = False
    assert not cfg.allowed("throttle")
    # empty binding = the game has no such control => blocked regardless of toggle
    cfg.profile.actions["throttle"] = True
    cfg.profile.bindings["throttle"] = ""
    assert not cfg.allowed("throttle")
    cfg.profile.bindings["throttle"] = "w"
    assert cfg.allowed("throttle")


def test_hazard_defaults_and_labels():
    assert "hazard" in C.ACTIONS
    assert C.ACTION_LABELS["hazard"].startswith("Hazard")
    assert "hazard" in C.DEFAULT_BINDINGS
    assert C.DEFAULT_BINDINGS["hazard"]


def test_plan_emits_hazard_on_hard_threat_stop():
    from roadmind.planner.planner import Planner
    from roadmind.perception.pipeline import WorldState
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "c.json"))
    p = Planner(cfg)
    allowed = {a for a in C.ACTIONS if cfg.allowed(a)}
    ws = WorldState()
    ws.lanes = {"valid": True, "offset": 0.0, "angle": 0.0}
    ws.speed_limit = 60
    ws.leader = {"x": 0.5, "y": 0.5, "w": 0.3, "h": 0.35, "label": "car", "id": 1}
    ws.leader_distance = 0.85
    ws.motion, ws.speed_est = 0.5, 0.6
    dt = p.plan(ws, allowed)
    assert dt.hazard is True
    assert dt.blinker_left is False and dt.blinker_right is False
    # clear road -> no hazards
    ws.leader = None
    ws.leader_distance = 0.0
    dt = p.plan(ws, allowed)
    assert dt.hazard is False
    # hazard whitelisted-off -> never
    cfg.profile.actions["hazard"] = False
    ws.leader = {"x": 0.5, "y": 0.5, "w": 0.3, "h": 0.35, "label": "car", "id": 1}
    ws.leader_distance = 0.85
    dt = p.plan(ws, {a for a in C.ACTIONS if cfg.allowed(a)})
    assert dt.hazard is False


def test_calibration_required_gate():
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "c.json"))
    assert cfg.is_calibrated() is False
    assert len(cfg.missing_calibration()) == 4        # all drive controls unprobed
    for a in C.CORE_CAL:
        cfg.profile.calibration[a] = C.CalibrationCurve(latency_ms=47.0)
    assert cfg.is_calibrated() is True
    assert cfg.missing_calibration() == []
    cfg.profile.calibration["throttle"] = C.CalibrationCurve(latency_ms=0.0)
    assert cfg.missing_calibration() == ["Throttle (gas)"]


def test_elevation_ok_default_on_this_os():
    # macOS / unset pid: always fine (no Windows UIPI there); on Windows the
    # real integrity comparison is exercised live instead
    assert sys_utils.game_elevation_ok(0) == (True, "")
    assert sys_utils.game_elevation_ok(None) == (True, "")


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


def test_world_and_model_roundtrip():
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "c.json"))
    cfg.profile.world.update({"horizon_y": 0.48, "dist_k": 8.2, "vpx": 0.44})
    cfg.profile.model = "s"
    cfg.save()
    cfg2 = C.RoadMindConfig(cfg.path)
    assert cfg2.profile.world["horizon_y"] == 0.48
    assert cfg2.profile.world["dist_k"] == 8.2
    assert cfg2.profile.world["vpx"] == 0.44
    assert cfg2.profile.model == "s"
    # bad model names are ignored
    cfg.profile.model = "xl"
    cfg.save()
    assert C.RoadMindConfig(cfg.path).profile.model in ("n", "s", "m")


def test_tracker_coasts_through_occlusion():
    from roadmind.perception.tracker import Tracker
    trk = Tracker()
    car = {"x": 0.5, "y": 0.6, "w": 0.2, "h": 0.3, "cls": 2, "label": "car",
           "conf": 0.9}
    trk.update([car])
    assert trk.tracks[0].hits == 1
    trk.update([dict(car, x=0.53)])   # moving right across the frame
    trk.update([dict(car, x=0.56)])
    track = trk.tracks[0]
    assert track.id == 0 and track.predicted is False
    assert track.vx > 0
    # object vanishes for a few frames: tracker must keep (coast) it
    trk.update([])
    assert trk.tracks and trk.tracks[0].predicted is True
    assert trk.tracks[0].occ == 1
    x_after = trk.tracks[0].x
    trk.update([])
    assert trk.tracks[0].occ == 2
    assert trk.tracks[0].x >= x_after          # keeps gliding at last velocity
    # reappears near the coasted position -> same identity, back live
    trk.update([dict(car, x=trk.tracks[0].x, y=trk.tracks[0].y)])
    assert trk.tracks[0].predicted is False
    assert trk.tracks[0].occ == 0
    assert trk.tracks[0].id == 0
    # long-gone ghosts get dropped entirely
    for _ in range(30):
        trk.update([])
    assert all(not t.predicted or t.occ <= 8 for t in trk.tracks)
    assert len([t for t in trk.tracks if t.id == 0]) == 0


def test_light_state_expires():
    import time as _t
    from roadmind.perception.pipeline import WorldState
    ws = WorldState()
    ws.light_state = "red"
    ws.light_ts = 0.0
    assert ws.has_red_light() is False           # stale red must NOT stop
    ws.light_ts = _t.time()
    assert ws.has_red_light() is True
    ws.light_state = "green"
    ws.light_ts = _t.time()
    assert ws.has_red_light() is False
    assert ws.has_green_light() is True
    ws.light_ts = _t.time() - 9.0
    assert ws.has_green_light() is False


def test_plan_respects_yellow_freshness():
    import time as _t
    from roadmind.planner.planner import Planner
    from roadmind.perception.pipeline import WorldState
    cfg = C.RoadMindConfig(os.path.join(tempfile.mkdtemp(), "c.json"))
    p = Planner(cfg)
    allowed = {a for a in C.ACTIONS if cfg.allowed(a)}
    ws = WorldState()
    ws.lanes = {"valid": True, "offset": 0.0, "angle": 0.0}
    ws.speed_limit = 60
    ws.motion, ws.speed_est = 0.5, 0.7
    ws.light_state = "yellow"
    ws.light_ts = _t.time()
    dt = p.plan(ws, allowed)
    assert dt.mode == "cautious"                 # fresh yellow eases off
    ws.light_ts = 0.0
    dt = p.plan(ws, allowed)
    assert dt.mode != "cautious"                 # stale yellow is ignored