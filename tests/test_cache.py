from satellite_x.cache import JsonCache
from satellite_x.errors import CacheMissError


def test_cache_key_is_order_independent(tmp_path):
    cache = JsonCache(tmp_path)
    assert cache.make_key("x", {"a": 1, "b": 2}) == cache.make_key(
        "x", {"b": 2, "a": 1}
    )


def test_cache_round_trip_and_miss(tmp_path):
    cache = JsonCache(tmp_path)
    cache.put("valid-key", {"value": 7})
    assert cache.get("valid-key") == {"value": 7}
    try:
        cache.get("missing")
    except CacheMissError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected CacheMissError")
