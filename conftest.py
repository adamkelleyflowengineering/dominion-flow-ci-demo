"""Tags every test with its Flow test case / requirement IDs in the JUnit XML.

Usage in tests:
    @pytest.mark.flow(test_case="TES-44190", requirements=["REQ-44098", "REQ-44084"])
    def test_x(flow_measure): flow_measure(212.0)
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "flow(test_case, requirements): Flow test case and requirement IDs")


@pytest.fixture(autouse=True)
def _flow_tags(request, record_property):
    marker = request.node.get_closest_marker("flow")
    if marker is not None:
        record_property("flow_test_case", marker.kwargs.get("test_case", ""))
        record_property("flow_requirements", ",".join(marker.kwargs.get("requirements", [])))


@pytest.fixture
def flow_measure(record_property):
    def _measure(value):
        record_property("flow_measured", value)
    return _measure
