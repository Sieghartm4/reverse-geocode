import os
from waitress import serve
from app import app

HOST = "0.0.0.0"
PORT = int(os.environ.get("FLASK_PORT", "5111"))
THREADS = int(os.environ.get("WAITRESS_THREADS", "64"))

if __name__ == "__main__":
    serve(app, host=HOST, port=PORT, threads=THREADS)
