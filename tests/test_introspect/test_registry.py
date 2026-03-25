import pytest

from model_ledger.core.exceptions import NoIntrospectorError
from model_ledger.introspect.models import IntrospectionResult
from model_ledger.introspect.registry import IntrospectorRegistry


class FakeIntrospector:
    name = "fake"

    def can_handle(self, obj):
        return isinstance(obj, dict)

    def introspect(self, obj):
        return IntrospectionResult(introspector="fake", algorithm="FakeAlgo")


class AnotherFakeIntrospector:
    name = "another"

    def can_handle(self, obj):
        return isinstance(obj, list)

    def introspect(self, obj):
        return IntrospectionResult(introspector="another")


def test_register_and_find():
    registry = IntrospectorRegistry()
    registry.register(FakeIntrospector())
    intro = registry.find({"key": "value"})
    assert intro.name == "fake"


def test_find_raises_no_introspector():
    registry = IntrospectorRegistry()
    with pytest.raises(NoIntrospectorError, match="str"):
        registry.find("unhandled")


def test_get_by_name():
    registry = IntrospectorRegistry()
    registry.register(FakeIntrospector())
    intro = registry.get_by_name("fake")
    assert intro.name == "fake"


def test_get_by_name_raises():
    registry = IntrospectorRegistry()
    with pytest.raises(NoIntrospectorError, match="nonexistent"):
        registry.get_by_name("nonexistent")


def test_deduplication_by_name():
    registry = IntrospectorRegistry()
    first = FakeIntrospector()
    second = FakeIntrospector()
    registry.register(first)
    registry.register(second)
    count = sum(1 for i in registry._introspectors if i.name == "fake")
    assert count == 1
    assert registry.get_by_name("fake") is second


def test_manual_registration_takes_priority():
    """Manually registered introspectors are prepended (higher priority)."""
    registry = IntrospectorRegistry()
    registry.register(AnotherFakeIntrospector())

    class BothHandler:
        name = "both"

        def can_handle(self, obj):
            return isinstance(obj, (dict, list))

        def introspect(self, obj):
            return IntrospectionResult(introspector="both")

    registry.register(BothHandler())
    # "both" was registered last but prepended, so it should be found first for lists
    intro = registry.find([1, 2, 3])
    assert intro.name == "both"
