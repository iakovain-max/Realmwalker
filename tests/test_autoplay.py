"""Short autoplay runs as part of the normal test suite (the full run happens at each milestone)."""

import pytest

from tools.autoplay import run_autoplay


@pytest.mark.slow
def test_autoplay_short_run(tmp_path):
    report = run_autoplay(turns=600, seed=3, home=tmp_path / "home")
    assert report.ok, report.summary()
