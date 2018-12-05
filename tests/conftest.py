import json

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--credentials_json",
        action="store",
        default=None,
        help="path to catmaid credentials in JSON form",
    )


@pytest.fixture
def credentials(request):
    cred_path = request.config.getoption("--credentials_json")

    if not cred_path:
        pytest.skip("No CATMAID credentials given")

    with open(cred_path) as f:
        return json.load(f)
