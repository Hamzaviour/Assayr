import sys

from assayr.windows.runner import SubprocessRunner


def test_an_unwritable_log_does_not_break_commands(tmp_path):
    log = tmp_path / "install.log"
    log.mkdir()  # opening a directory as a file fails, like a log the process may not write
    result = SubprocessRunner(log).run([sys.executable, "-c", "print('ok')"])
    assert result.returncode == 0 and "ok" in result.stdout
