from importlib import resources

from pathlib import Path


def get_fixture_path(fixture_name: str = "") -> Path:
    ref = resources.files(__name__) / fixture_name
    with resources.as_file(ref) as path:
        return path
