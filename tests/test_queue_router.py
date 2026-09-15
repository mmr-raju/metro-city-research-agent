from graph import queue_router


def test_loop_when_cities_remain(cities):
    assert queue_router({"city_queue": cities}) == "researcher"


def test_exit_when_empty():
    assert queue_router({"city_queue": []}) == "finalizer"
