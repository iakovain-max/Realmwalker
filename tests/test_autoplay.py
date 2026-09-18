"""Short autoplay runs as part of the normal test suite (the full run happens at each milestone)."""

import pytest

from tools.autoplay import run_autoplay


@pytest.mark.parametrize("ai", ["off", "mock"])
def test_autoplay_short_run(ai, tmp_path):
    report = run_autoplay(turns=600, seed=3, ai=ai, home=tmp_path / "home")
    assert report.ok, report.summary()
