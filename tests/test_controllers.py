"""Tests for the baseline and smart irrigation controllers."""

from __future__ import annotations

import pytest

from aquareserve.config.schema import GrowthStage, ReserveStrategy
from aquareserve.controllers import (
    FixedScheduleController,
    RainfedController,
    SmartCriticalStageController,
    ThresholdController,
)
from aquareserve.controllers.base import ZoneControlContext


def ctx(depletion_mm=0.0, raw_mm=50.0, taw_mm=100.0, day=0, strategy=ReserveStrategy.RAINFED, stage_ky=0.0, stage=GrowthStage.MID):

    return ZoneControlContext(
        zone_id="z", day_in_season=day, stage=stage,
        depletion_mm=depletion_mm, raw_mm=raw_mm, taw_mm=taw_mm,
        et0_mm=5.0, crop_et_mm=5.0, days_since_irrigation=99,
        max_application_rate_mm_per_day=20.0, strategy=strategy, stage_ky=stage_ky,
    )


def test_rainfed_never_irrigates():
    c = RainfedController()

    assert c.request_mm(ctx(depletion_mm=90.0)) == 0.0
    assert c.name == "rainfed"


def test_fixed_schedule_triggers_on_interval():
    c = FixedScheduleController(depth_mm=15.0, interval_days=7)

    assert c.request_mm(ctx(day=0)) == 15.0
    assert c.request_mm(ctx(day=3)) == 0.0
    assert c.request_mm(ctx(day=7)) == 15.0
    assert c.request_mm(ctx(day=14)) == 15.0


def test_fixed_schedule_validates():
    with pytest.raises(ValueError):
        FixedScheduleController(interval_days=0)

    with pytest.raises(ValueError):
        FixedScheduleController(depth_mm=-1)


def test_threshold_refills_when_raw_reached():
    c = ThresholdController()

    assert c.request_mm(ctx(depletion_mm=40.0, raw_mm=50.0)) == 0.0
    assert c.request_mm(ctx(depletion_mm=60.0, raw_mm=50.0)) == 60.0


def test_threshold_custom_fraction():
    c = ThresholdController(trigger_fraction=0.3)

    assert c.request_mm(ctx(depletion_mm=25.0, taw_mm=100.0)) == 0.0
    assert c.request_mm(ctx(depletion_mm=35.0, taw_mm=100.0)) == 35.0

    with pytest.raises(ValueError):
        ThresholdController(trigger_fraction=1.5)


# --- Smart critical-stage controller (D2) --------------------------------------
def test_smart_rainfed_zone_never_irrigates():
    c = SmartCriticalStageController()

    assert c.request_mm(ctx(depletion_mm=90.0, strategy=ReserveStrategy.RAINFED)) == 0.0


def test_smart_near_full_backup_keeps_topped_up():
    c = SmartCriticalStageController()
    s = ReserveStrategy.NEAR_FULL_BACKUP

    assert c.request_mm(ctx(depletion_mm=40.0, raw_mm=50.0, strategy=s)) == 0.0
    assert c.request_mm(ctx(depletion_mm=60.0, raw_mm=50.0, strategy=s)) == 60.0


def test_smart_cereal_waters_only_critical_stressed():
    c = SmartCriticalStageController(critical_ky=0.6)
    s = ReserveStrategy.CRITICAL_STAGE_DEFICIT

    # critical stage (high Ky) AND stressed -> irrigate
    assert c.request_mm(ctx(depletion_mm=60.0, raw_mm=50.0, strategy=s, stage_ky=1.05)) == 60.0

    # critical stage but not stressed -> wait
    assert c.request_mm(ctx(depletion_mm=40.0, raw_mm=50.0, strategy=s, stage_ky=1.05)) == 0.0
    
    # stressed but non-critical stage -> save the water
    assert c.request_mm(ctx(depletion_mm=60.0, raw_mm=50.0, strategy=s, stage_ky=0.2)) == 0.0


def test_smart_validates_critical_ky():
    with pytest.raises(ValueError):
        SmartCriticalStageController(critical_ky=0.0)
