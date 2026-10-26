from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from helpers.local import LocalDisplay


def test_display_reads_files_preserves_queries_and_blocks_escapes(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    page = root / "view.html"
    page.write_text("<p>Display</p>")
    outside = tmp_path / "private.txt"
    outside.write_text("outside")
    (root / "link.txt").symlink_to(outside)
    with LocalDisplay(root) as display:
        assert (
            urlopen(display.url("view.html?view=context")).read() == page.read_bytes()
        )
        assert display.url(page).startswith("http://127.0.0.1:")
        for path in ("../private.txt", "link.txt"):
            with pytest.raises(ValueError):
                display.url(path)
        for path in ("../private.txt", "%2e%2e/private.txt", "link.txt", ""):
            with pytest.raises(HTTPError) as error:
                urlopen(display.base_url + path)
            assert error.value.code == 404
    with pytest.raises(ValueError, match="closed"):
        display.url(page)
