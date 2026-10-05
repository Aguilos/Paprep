try:
    import gevent.monkey
    gevent.monkey.patch_all()
except ImportError:
    import eventlet
    eventlet.monkey_patch()

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    print("\n" + "=" * 55)
    print("  🚀 PaPrep Server is starting...")
    print("  👉 Open in your browser: http://localhost:5000")
    print("  👉 Alternative URL:     http://127.0.0.1:5000")
    print("  ℹ️  Press CTRL+C to quit / stop the server")
    print("=" * 55 + "\n", flush=True)

    # Use SocketIO runner to support WebSocket connections in development
    # Disable the auto-reloader so monkey-patching happens cleanly in the main process
    socketio.run(app, debug=True, use_reloader=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

