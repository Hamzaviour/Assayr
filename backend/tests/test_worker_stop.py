import signal

from assayr import cli


def test_stop_flag_set_by_signal_handler():
    flag = cli.StopFlag()
    flag.install()
    try:
        handler = signal.getsignal(signal.SIGINT)
        handler(signal.SIGINT, None)
        assert flag.requested
    finally:
        flag.restore()


def test_worker_finishes_current_job_then_exits(monkeypatch):
    calls = []
    flag = cli.StopFlag()

    def fake_run_one(make_session, env):
        calls.append("job")
        flag.requested = True  # stop arrives while a job runs
        return True

    monkeypatch.setattr(cli, "run_one", fake_run_one)
    monkeypatch.setattr(cli, "_enqueue_recompute", lambda database: None)
    cli._worker_loop(database=None, env=None, settings=cli.get_settings(), flag=flag)
    assert calls == ["job"]
