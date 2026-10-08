import socket
import struct
import threading

import pytest

from assayr.verification.av import scan_file

EICAR_MARKER = b"EICAR-TEST"


def _fake_clamd(reply_for):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve():
        conn, _ = server.accept()
        with conn:
            command = b""
            while not command.endswith(b"\0"):
                command += conn.recv(1)
            assert command == b"zINSTREAM\0"
            data = b""
            while True:
                (size,) = struct.unpack("!I", conn.recv(4, socket.MSG_WAITALL))
                if size == 0:
                    break
                data += conn.recv(size, socket.MSG_WAITALL)
            conn.sendall(reply_for(data))
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1]


@pytest.fixture
def sample(tmp_path):
    def make(content):
        path = tmp_path / "f.bin"
        path.write_bytes(content)
        return path

    return make


def reply(data):
    return b"stream: Eicar-Signature FOUND\0" if EICAR_MARKER in data else b"stream: OK\0"


def test_clean_file(sample):
    assert scan_file(sample(b"hello" * 50_000), "127.0.0.1", _fake_clamd(reply)).status == "clean"


def test_infected_file_reports_the_signature(sample):
    result = scan_file(sample(b"x" + EICAR_MARKER), "127.0.0.1", _fake_clamd(reply))
    assert (result.status, result.signature) == ("infected", "Eicar-Signature")


def test_unreachable_scanner_is_an_error(sample):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    assert scan_file(sample(b"x"), "127.0.0.1", free_port, timeout=1).status == "error"
