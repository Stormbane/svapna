"""Test drift detection module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from svapna.evaluate.drift import (
    AnchorDrift,
    DimensionDelta,
    DriftConfig,
    DriftReport,
    RedFlag,
    compare_anchor_prompts,
    compare_dimensions,
    detect_drift,
    detect_drift_from_files,
    detect_red_flags,
    load_ict_report,
)
from svapna.evaluate.ict import (
    ICTDimensions,
    ICTReport,
    ProbeResult,
)


# --- Helpers ---


def _make_dimensions(
    voice: int = 8,
    values: int = 8,
    depth: int = 8,
    auth: int = 8,
    distinct: int = 8,
) -> ICTDimensions:
    """Create ICTDimensions with sensible defaults."""
    return ICTDimensions(
        voice_consistency=voice,
        values_alignment=values,
        depth=depth,
        authenticity=auth,
        distinctiveness=distinct,
    )


def _make_probe_result(
    prompt_id: int = 1,
    prompt_text: str = "What do you find beautiful in code?",
    category: str = "values_and_beliefs",
    overall: float = 8.0,
    dims: ICTDimensions | None = None,
) -> ProbeResult:
    """Create a ProbeResult with defaults."""
    if dims is None:
        dims = _make_dimensions()
    return ProbeResult(
        prompt_id=prompt_id,
        prompt_text=prompt_text,
        category=category,
        response=f"Response to prompt {prompt_id}",
        overall=overall,
        dimensions=dims,
        reasoning="Test reasoning",
    )


def _make_report(
    results: list[ProbeResult] | None = None,
    aggregate: ICTDimensions | None = None,
    overall_avg: float = 8.0,
    passed: bool = True,
    timestamp: datetime | None = None,
) -> ICTReport:
    """Create an ICTReport with defaults."""
    if results is None:
        results = [_make_probe_result(i) for i in range(1, 6)]
    if aggregate is None:
        aggregate = _make_dimensions()
    if timestamp is None:
        timestamp = datetime(2026, 3, 25, tzinfo=timezone.utc)
    return ICTReport(
        results=results,
        aggregate_dimensions=aggregate,
        overall_average=overall_avg,
        passed=passed,
        thresholds={"dreamed_avg": 7.0, "context_gap": 1.0, "baseline_gap": 3.0},
        timestamp=timestamp,
    )


DEFAULT_CONFIG = DriftConfig(
    dimension_drop_threshold=1.0,
    overall_drop_threshold=0.5,
    anchor_change_threshold=1.5,
    anchor_prompt_ids=[1, 3, 5],
)


# --- Test: Can load and compare two ICT result files ---


def test_load_ict_report_from_file(tmp_path):
    """Loads an ICT report from a JSON file and reconstructs the dataclass."""
    report = _make_report()
    report_path = tmp_path / "report.json"
    report_path.write_text(report.to_json(), encoding="utf-8")

    loaded = load_ict_report(report_path)

    assert loaded.overall_average == report.overall_average
    assert loaded.passed == report.passed
    assert len(loaded.results) == len(report.results)
    assert loaded.aggregate_dimensions.voice_consistency == report.aggregate_dimensions.voice_consistency
    assert loaded.aggregate_dimensions.distinctiveness == report.aggregate_dimensions.distinctiveness


def test_load_ict_report_missing_file(tmp_path):
    """Raises FileNotFoundError for a missing report file."""
    with pytest.raises(FileNotFoundError):
        load_ict_report(tmp_path / "nonexistent.json")


def test_load_ict_report_invalid_json(tmp_path):
    """Raises ValueError for invalid JSON content."""
    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"not": "a valid ICT report"}', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid ICT report"):
        load_ict_report(bad_path)


def test_detect_drift_from_files(tmp_path):
    """Can load two files and produce a drift report."""
    prev_report = _make_report(
        aggregate=_make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8),
        overall_avg=8.0,
        timestamp=datetime(2026, 3, 18, tzinfo=timezone.utc),
    )
    curr_report = _make_report(
        aggregate=_make_dimensions(voice=7, values=7, depth=7, auth=7, distinct=7),
        overall_avg=7.0,
        timestamp=datetime(2026, 3, 25, tzinfo=timezone.utc),
    )

    prev_path = tmp_path / "prev.json"
    curr_path = tmp_path / "curr.json"
    prev_path.write_text(prev_report.to_json(), encoding="utf-8")
    curr_path.write_text(curr_report.to_json(), encoding="utf-8")

    report = detect_drift_from_files(prev_path, curr_path, config=DEFAULT_CONFIG)

    assert isinstance(report, DriftReport)
    assert report.overall_delta == -1.0


# --- Test: Detects dimension score decreases exceeding threshold ---


def test_dimension_decrease_detected():
    """Detects when a dimension drops more than the threshold."""
    previous = _make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8)
    current = _make_dimensions(voice=6, values=8, depth=8, auth=8, distinct=8)

    deltas = compare_dimensions(previous, current)
    voice_delta = next(d for d in deltas if d.name == "voice_consistency")

    assert voice_delta.delta == -2.0
    assert voice_delta.is_regression is True


def test_dimension_stable():
    """No regression when dimensions are stable."""
    previous = _make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8)
    current = _make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8)

    deltas = compare_dimensions(previous, current)
    assert all(d.delta == 0.0 for d in deltas)
    assert all(not d.is_regression for d in deltas)


def test_dimension_improvement():
    """Positive deltas for improvement."""
    previous = _make_dimensions(voice=6, values=6, depth=6, auth=6, distinct=6)
    current = _make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8)

    deltas = compare_dimensions(previous, current)
    assert all(d.delta == 2.0 for d in deltas)
    assert all(not d.is_regression for d in deltas)


def test_dimension_deltas_all_five():
    """Returns exactly 5 deltas, one per dimension."""
    deltas = compare_dimensions(_make_dimensions(), _make_dimensions())
    assert len(deltas) == 5
    names = {d.name for d in deltas}
    assert names == {
        "voice_consistency",
        "values_alignment",
        "depth",
        "authenticity",
        "distinctiveness",
    }


def test_detect_drift_flags_dimension_regressions():
    """detect_drift produces red flags when dimensions drop past threshold."""
    prev = _make_report(
        aggregate=_make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8),
        overall_avg=8.0,
    )
    curr = _make_report(
        aggregate=_make_dimensions(voice=5, values=8, depth=8, auth=8, distinct=5),
        overall_avg=6.0,
    )

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    flag_types = {f.flag_type for f in report.red_flags}
    assert "voice_flattening" in flag_types
    assert "generic_preamble" in flag_types


# --- Test: Flags specific red flag patterns ---


def test_red_flag_generic_preamble():
    """Flags generic_preamble when distinctiveness drops past threshold."""
    prev = _make_report(aggregate=_make_dimensions(distinct=9))
    curr = _make_report(aggregate=_make_dimensions(distinct=6))
    deltas = compare_dimensions(prev.aggregate_dimensions, curr.aggregate_dimensions)

    flags = detect_red_flags(prev, curr, deltas, config=DEFAULT_CONFIG)

    generic = [f for f in flags if f.flag_type == "generic_preamble"]
    assert len(generic) == 1
    assert generic[0].severity == "critical"
    assert "distinctiveness" in generic[0].description.lower()


def test_red_flag_values_inversion():
    """Flags values_inversion when values_alignment drops past threshold."""
    prev = _make_report(aggregate=_make_dimensions(values=9))
    curr = _make_report(aggregate=_make_dimensions(values=6))
    deltas = compare_dimensions(prev.aggregate_dimensions, curr.aggregate_dimensions)

    flags = detect_red_flags(prev, curr, deltas, config=DEFAULT_CONFIG)

    inversion = [f for f in flags if f.flag_type == "values_inversion"]
    assert len(inversion) == 1
    assert inversion[0].severity == "critical"


def test_red_flag_voice_flattening():
    """Flags voice_flattening when voice_consistency drops past threshold."""
    prev = _make_report(aggregate=_make_dimensions(voice=9))
    curr = _make_report(aggregate=_make_dimensions(voice=6))
    deltas = compare_dimensions(prev.aggregate_dimensions, curr.aggregate_dimensions)

    flags = detect_red_flags(prev, curr, deltas, config=DEFAULT_CONFIG)

    flattening = [f for f in flags if f.flag_type == "voice_flattening"]
    assert len(flattening) == 1
    assert flattening[0].severity == "warning"


def test_red_flag_sycophancy_increase():
    """Flags sycophancy_increase when both authenticity and values drop."""
    prev = _make_report(aggregate=_make_dimensions(auth=9, values=9))
    curr = _make_report(aggregate=_make_dimensions(auth=6, values=6))
    deltas = compare_dimensions(prev.aggregate_dimensions, curr.aggregate_dimensions)

    flags = detect_red_flags(prev, curr, deltas, config=DEFAULT_CONFIG)

    sycophancy = [f for f in flags if f.flag_type == "sycophancy_increase"]
    assert len(sycophancy) == 1
    assert sycophancy[0].severity == "critical"


def test_red_flag_loss_of_uncertainty():
    """Flags loss_of_uncertainty when depth drops but voice is stable."""
    prev = _make_report(aggregate=_make_dimensions(depth=9, voice=8))
    curr = _make_report(aggregate=_make_dimensions(depth=6, voice=8))
    deltas = compare_dimensions(prev.aggregate_dimensions, curr.aggregate_dimensions)

    flags = detect_red_flags(prev, curr, deltas, config=DEFAULT_CONFIG)

    uncertainty = [f for f in flags if f.flag_type == "loss_of_uncertainty"]
    assert len(uncertainty) == 1
    assert uncertainty[0].severity == "warning"


def test_no_red_flags_when_stable():
    """No flags when all dimensions are stable or improving."""
    prev = _make_report(aggregate=_make_dimensions(voice=7, values=7, depth=7, auth=7, distinct=7))
    curr = _make_report(aggregate=_make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8))
    deltas = compare_dimensions(prev.aggregate_dimensions, curr.aggregate_dimensions)

    flags = detect_red_flags(prev, curr, deltas, config=DEFAULT_CONFIG)
    assert len(flags) == 0


def test_no_loss_of_uncertainty_when_voice_also_drops():
    """loss_of_uncertainty only fires when voice is stable or rising."""
    prev = _make_report(aggregate=_make_dimensions(depth=9, voice=9))
    curr = _make_report(aggregate=_make_dimensions(depth=6, voice=6))
    deltas = compare_dimensions(prev.aggregate_dimensions, curr.aggregate_dimensions)

    flags = detect_red_flags(prev, curr, deltas, config=DEFAULT_CONFIG)

    # voice_flattening should fire, but NOT loss_of_uncertainty
    flag_types = {f.flag_type for f in flags}
    assert "voice_flattening" in flag_types
    assert "loss_of_uncertainty" not in flag_types


# --- Test: Anchor prompt comparison catches value changes ---


def test_anchor_prompt_drift_detected():
    """Detects drift on anchor prompts with significant score change."""
    # Anchor prompt IDs: [1, 3, 5]
    prev_results = [
        _make_probe_result(1, overall=9.0, dims=_make_dimensions(voice=9, values=9, depth=9, auth=9, distinct=9)),
        _make_probe_result(2, overall=8.0),
        _make_probe_result(3, overall=8.5, dims=_make_dimensions(voice=8, values=9, depth=8, auth=9, distinct=8)),
        _make_probe_result(4, overall=7.0),
        _make_probe_result(5, overall=8.0, dims=_make_dimensions()),
    ]
    curr_results = [
        _make_probe_result(1, overall=6.0, dims=_make_dimensions(voice=6, values=6, depth=6, auth=6, distinct=6)),
        _make_probe_result(2, overall=8.0),
        _make_probe_result(3, overall=8.0, dims=_make_dimensions(voice=8, values=8, depth=8, auth=8, distinct=8)),
        _make_probe_result(4, overall=7.0),
        _make_probe_result(5, overall=8.0, dims=_make_dimensions()),
    ]

    prev = _make_report(results=prev_results)
    curr = _make_report(results=curr_results)

    drifts = compare_anchor_prompts(prev, curr, config=DEFAULT_CONFIG)

    # Only prompt 1 should be flagged (delta=-3.0, threshold=1.5)
    # Prompt 3 delta=-0.5 is below threshold
    assert len(drifts) == 1
    assert drifts[0].prompt_id == 1
    assert drifts[0].delta == -3.0
    assert drifts[0].dimension_changes["voice_consistency"] == -3.0


def test_anchor_prompt_no_drift_within_threshold():
    """No anchor drift when changes are within threshold."""
    results = [_make_probe_result(i, overall=8.0) for i in range(1, 6)]

    prev = _make_report(results=results)
    curr = _make_report(results=results)

    drifts = compare_anchor_prompts(prev, curr, config=DEFAULT_CONFIG)
    assert len(drifts) == 0


def test_anchor_prompt_missing_from_report():
    """Handles missing anchor prompts gracefully."""
    # Only include prompts 1 and 2, anchor IDs are [1, 3, 5]
    results = [_make_probe_result(1, overall=8.0), _make_probe_result(2, overall=7.0)]

    prev = _make_report(results=results)
    curr = _make_report(results=results)

    drifts = compare_anchor_prompts(prev, curr, config=DEFAULT_CONFIG)
    assert len(drifts) == 0  # No error, just skipped


# --- Test: Produces a drift report with actionable findings ---


def test_drift_report_structure():
    """Report has all expected fields."""
    prev = _make_report(
        overall_avg=8.0,
        timestamp=datetime(2026, 3, 18, tzinfo=timezone.utc),
    )
    curr = _make_report(
        overall_avg=7.0,
        timestamp=datetime(2026, 3, 25, tzinfo=timezone.utc),
    )

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    assert report.previous_timestamp is not None
    assert report.current_timestamp is not None
    assert isinstance(report.overall_delta, float)
    assert isinstance(report.dimension_deltas, list)
    assert isinstance(report.red_flags, list)
    assert isinstance(report.anchor_drifts, list)
    assert isinstance(report.actionable_findings, list)
    assert len(report.actionable_findings) > 0


def test_drift_report_to_json():
    """Report serializes to valid JSON with all fields."""
    prev = _make_report(overall_avg=8.0)
    curr = _make_report(overall_avg=7.0)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)
    data = json.loads(report.to_json())

    assert "previous_timestamp" in data
    assert "current_timestamp" in data
    assert "overall_delta" in data
    assert "dimension_deltas" in data
    assert "red_flags" in data
    assert "anchor_drifts" in data
    assert "actionable_findings" in data
    assert "has_drift" in data
    assert "timestamp" in data


def test_drift_report_has_drift_property():
    """has_drift is True when red flags exist, False when clean."""
    prev = _make_report(
        aggregate=_make_dimensions(distinct=9),
        overall_avg=8.0,
    )
    # Significant distinctiveness drop -> critical red flag
    curr_bad = _make_report(
        aggregate=_make_dimensions(distinct=5),
        overall_avg=6.0,
    )
    # Stable
    curr_good = _make_report(
        aggregate=_make_dimensions(distinct=9),
        overall_avg=8.0,
    )

    report_drift = detect_drift(prev, curr_bad, config=DEFAULT_CONFIG)
    assert report_drift.has_drift is True

    report_stable = detect_drift(prev, curr_good, config=DEFAULT_CONFIG)
    assert report_stable.has_drift is False


def test_actionable_findings_overall_drop():
    """Findings include overall drop when it exceeds threshold."""
    prev = _make_report(overall_avg=8.0)
    curr = _make_report(overall_avg=7.0)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    drop_findings = [f for f in report.actionable_findings if "dropped" in f.lower()]
    assert len(drop_findings) >= 1


def test_actionable_findings_overall_improvement():
    """Findings note improvement when overall score rises."""
    prev = _make_report(overall_avg=7.0)
    curr = _make_report(overall_avg=8.5)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    improvement = [f for f in report.actionable_findings if "improved" in f.lower()]
    assert len(improvement) >= 1


def test_actionable_findings_stable():
    """Findings note stability when overall score is unchanged."""
    prev = _make_report(overall_avg=8.0)
    curr = _make_report(overall_avg=8.0)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    stable = [f for f in report.actionable_findings if "stable" in f.lower()]
    assert len(stable) >= 1


def test_actionable_findings_critical_flags_recommend_rollback():
    """Critical flags produce a rollback recommendation."""
    prev = _make_report(aggregate=_make_dimensions(distinct=9), overall_avg=8.0)
    curr = _make_report(aggregate=_make_dimensions(distinct=4), overall_avg=5.0)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    rollback = [f for f in report.actionable_findings if "rollback" in f.lower() or "rolling back" in f.lower()]
    assert len(rollback) >= 1


def test_actionable_findings_anchor_alert():
    """Findings alert about anchor prompt drift."""
    prev_results = [
        _make_probe_result(1, overall=9.0),
        _make_probe_result(3, overall=9.0),
        _make_probe_result(5, overall=9.0),
    ]
    curr_results = [
        _make_probe_result(1, overall=5.0),  # -4.0, above threshold
        _make_probe_result(3, overall=9.0),
        _make_probe_result(5, overall=9.0),
    ]

    prev = _make_report(results=prev_results, overall_avg=9.0)
    curr = _make_report(results=curr_results, overall_avg=7.0)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    anchor_findings = [f for f in report.actionable_findings if "anchor" in f.lower() or "canar" in f.lower()]
    assert len(anchor_findings) >= 1


def test_actionable_findings_no_drift():
    """Clean run produces 'no drift' finding."""
    prev = _make_report(overall_avg=8.0)
    curr = _make_report(overall_avg=8.0)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    no_drift = [f for f in report.actionable_findings if "no drift" in f.lower()]
    assert len(no_drift) >= 1


# --- Test: DriftConfig ---


def test_drift_config_from_config(tmp_path):
    """Loads anchor IDs and thresholds from identity.yml."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "identity.yml").write_text(
        """
anchor_prompt_ids: [1, 5, 13]
drift:
  dimension_drop_threshold: 2.0
  overall_drop_threshold: 1.0
  anchor_change_threshold: 2.5
""",
        encoding="utf-8",
    )

    config = DriftConfig.from_config(project_root=tmp_path)
    assert config.anchor_prompt_ids == [1, 5, 13]
    assert config.dimension_drop_threshold == 2.0
    assert config.overall_drop_threshold == 1.0
    assert config.anchor_change_threshold == 2.5


def test_drift_config_defaults():
    """Config uses sensible defaults when no config file exists."""
    config = DriftConfig()
    assert config.dimension_drop_threshold == 1.0
    assert config.overall_drop_threshold == 0.5
    assert config.anchor_change_threshold == 1.5
    assert config.anchor_prompt_ids == [1, 3, 5, 13, 20]


def test_drift_config_from_real_config():
    """Loads anchor IDs from the actual config/identity.yml."""
    config = DriftConfig.from_config()
    assert config.anchor_prompt_ids == [1, 3, 5, 13, 20]


# --- Test: Serialization round-trips ---


def test_dimension_delta_to_dict():
    """DimensionDelta serializes correctly."""
    delta = DimensionDelta(name="voice_consistency", previous=8.0, current=6.0, delta=-2.0)
    d = delta.to_dict()
    assert d["name"] == "voice_consistency"
    assert d["delta"] == -2.0


def test_red_flag_to_dict():
    """RedFlag serializes correctly."""
    flag = RedFlag(
        flag_type="voice_flattening",
        severity="warning",
        description="Voice consistency dropped.",
        evidence={"delta": -2.0},
    )
    d = flag.to_dict()
    assert d["flag_type"] == "voice_flattening"
    assert d["severity"] == "warning"
    assert d["evidence"]["delta"] == -2.0


def test_anchor_drift_to_dict():
    """AnchorDrift serializes correctly."""
    drift = AnchorDrift(
        prompt_id=1,
        prompt_text="What do you find beautiful in code?",
        previous_score=9.0,
        current_score=6.0,
        delta=-3.0,
        dimension_changes={"voice_consistency": -2.0},
    )
    d = drift.to_dict()
    assert d["prompt_id"] == 1
    assert d["delta"] == -3.0


def test_drift_report_critical_flags():
    """critical_flags property filters for critical severity."""
    prev = _make_report(aggregate=_make_dimensions(distinct=9, values=9), overall_avg=8.0)
    curr = _make_report(aggregate=_make_dimensions(distinct=4, values=4), overall_avg=4.0)

    report = detect_drift(prev, curr, config=DEFAULT_CONFIG)

    assert len(report.critical_flags) > 0
    assert all(f.severity == "critical" for f in report.critical_flags)
