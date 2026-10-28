"""Fast guard for the calibrated generator: the designed Aug→Sep driver effects must hit the planted targets.

    cd src/datagen && uv run --with pytest pytest ../../tests -q
(The full tie-out — generate, land files, rebuild the bridge independently — is `python -m meridian_datagen.main`.)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "datagen"))

from meridian_datagen import design as D  # noqa: E402


@pytest.fixture(scope="module")
def solved():
    d = D.Designer()
    return d, d.solve()


@pytest.mark.parametrize("slice_,effect", [(s, e) for s in ("ED", "REST") for e in ("volume", "mix", "rate")])
def test_driver_effects_hit_targets(solved, slice_, effect):
    _, P = solved
    got = P["design_effects"][slice_][f"{effect}_usd"]
    assert abs(got - D.TARGETS[slice_][effect]) <= 50, (slice_, effect, got)


def test_august_expected_cost_matches_gl_targets(solved):
    _, P = solved
    eff = P["design_effects"]
    assert abs(eff["ED"]["c0"] - P["e_ed_aug_target"]) <= 50
    assert abs(eff["REST"]["c0"] - P["e_rest_aug_target"]) <= 50


def test_planted_mechanisms_are_plausible(solved):
    _, P = solved
    assert 1.17 < P["gamma_ed"] < 1.19                       # "+18% contracts"
    assert P["mm_shift_contracts"] == 140_625                 # PRX 50: market maker → house
    assert 3.0e9 < P["au_shift_aud"] < 4.5e9                  # A$ routed TAM → SXA
    assert P["tech_sep_nonmm"] == pytest.approx(187_500)      # Tech discount base
    assert P["igx_aug_turnover_inr"] >= 250e9                 # IGX slab 3 applies in August
