from pkg_resources import resource_filename

from pathlib import Path


def get_fixture_path(fixture_name: str = "") -> Path:
    return Path(
        resource_filename(__name__, fixture_name),
    )
