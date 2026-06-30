import os
import socket
from waitress import serve
from app import app

HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
PORT = int(os.environ.get("FLASK_PORT", "5111"))
THREADS = int(os.environ.get("WAITRESS_THREADS", "16"))


def _validate_bind_address(host: str) -> str:
    """Return a bindable host. Falls back to '0.0.0.0' if the address is invalid."""
    # Quick accept common addresses
    if host in ("0.0.0.0", "::", "", "localhost", "127.0.0.1"):
        return host

    sock = None
    try:
        # Try to bind a temporary socket to the requested address on an ephemeral port.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return host
    except OSError:
        print(f"[warning] Requested FLASK_HOST={host} is not valid on this machine; falling back to 0.0.0.0")
        return "0.0.0.0"
    finally:
        if sock is not None:
            sock.close()


if __name__ == "__main__":
    HOST = _validate_bind_address(HOST)
    serve(app, host=HOST, port=PORT, threads=THREADS)
