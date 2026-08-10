Deployment Notes for real-time Socket.IO feature

1) Install production dependencies

Ensure you install dependencies including `eventlet` and `flask-socketio`:

```bash
pip install -r requirements.txt
```

2) Gunicorn command (single-process Eventlet worker)

Run the app with Gunicorn using the `eventlet` worker class. The entrypoint is `run:app` (the `run.py` module exposes `app`):

```bash
gunicorn -k eventlet -w 1 run:app
```

Notes:
- `-k eventlet` uses the Eventlet worker which supports WebSocket transports.
- `-w 1` runs a single worker process. Socket.IO with in-process eventlet does not provide cross-process pub/sub by default.

3) Reverse proxy / load balancer

If you place a reverse proxy (nginx, AWS ALB, etc.) in front of the app, ensure it is configured to allow WebSocket upgrade headers and not block `Connection: upgrade` / `Upgrade: websocket` headers. Example minimal nginx location block excerpt:

```
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_http_version 1.1;
proxy_set_header Host $host;
```

4) Worker scaling limitation (single worker explained)

- By default this setup runs with a single eventlet worker (`-w 1`). If you increase the number of Gunicorn workers without adding an external message broker (e.g., Redis) and configuring Socket.IO to use it, each worker process will have its own in-memory socket registry. Emitted events from one worker will not automatically reach clients connected to other worker processes.
- To scale to multiple workers while preserving real-time event broadcast across processes, you must configure a message queue/pub-sub backend (e.g., Redis) and initialize the Socket.IO server with that message queue. That is outside the scope of this change but is a recommended future step if you need horizontal scaling.

5) Local dev

- `run.py` now monkey-patches with Eventlet if available so the same code path works locally when `eventlet` is installed.
- For development you can still run:

```bash
python run.py
```

which will start the Socket.IO-aware server via `socketio.run(...)`.

6) Summary

- Use `gunicorn -k eventlet -w 1 run:app` to deploy with WebSocket support.
- Ensure your proxy supports WebSocket upgrades.
- Understand the single-worker limitation and plan Redis/pubsub if you need multi-worker scaling in future.

---

Scaling to Multiple Workers (NOT YET IMPLEMENTED — REFERENCE ONLY)
---------------------------------------------------------------

This section documents how you *would* scale Socket.IO across multiple Gunicorn workers using Redis as the message queue. Do not apply these changes to the running app unless you also provision and configure a Redis instance and update your deployment accordingly.

Why this is needed
- Each Gunicorn worker is a separate process with its own in-memory Socket.IO client/room registry. Without a shared message queue, emits from one worker do not reach clients connected to other workers. A central message broker (Redis) allows workers to publish/subscribe events so broadcasts reach all connected clients across processes.

Example code change (reference only)
-----------------------------------
You would initialize the Socket.IO server to use Redis as the message queue. Example:

```python
# reference-only: shows how to enable Redis message queue
from flask_socketio import SocketIO

# when creating SocketIO (either in app factory or at module level)
socketio = SocketIO(app, message_queue='redis://localhost:6379/0')
```

Requirements change (reference only)
-----------------------------------
You would add the Redis client dependency to `requirements.txt` (reference only):

```
redis
```

Gunicorn command for multi-worker deployment (reference only)
-----------------------------------------------------------
Once Redis is configured and reachable by your application, you can run multiple Eventlet workers. Example:

```bash
gunicorn -k eventlet -w 4 run:app
```

Prerequisites and notes
- This requires a running Redis instance (local, self-hosted, or managed add-on) reachable at the URL you specify.
- You must ensure network access and credentials/security for Redis are handled appropriately.
- Label: NOT YET IMPLEMENTED — REFERENCE ONLY. Do not assume the app currently uses Redis or that multiple-worker broadcasts work until you implement and configure the changes above.

End of reference section.
