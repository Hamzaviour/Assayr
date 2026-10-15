import pytest

from assayr.healthcheck import HealthError, wait_healthy


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_returns_when_healthy_after_retries():
    replies = iter([OSError("refused"), {"status": "starting"}, {"status": "ok", "version": "0.3.0"}])

    def fetch(url):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    clock = Clock()
    assert (
        wait_healthy("https://localhost/api/v1/healthz", 60, "0.3.0", fetch, clock.sleep, clock.now)
        == "0.3.0"
    )


def test_wrong_version_times_out_with_reason():
    clock = Clock()
    with pytest.raises(HealthError, match="0.2.0"):
        wait_healthy("u", 10, "0.3.0", lambda u: {"status": "ok", "version": "0.2.0"}, clock.sleep, clock.now)
