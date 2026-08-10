try:
    import eventlet
    eventlet.monkey_patch()
except Exception:
    eventlet = None

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    # Use SocketIO runner to support WebSocket connections in development
    # Disable the auto-reloader so monkey-patching happens cleanly in the main process
    socketio.run(app, debug=True, use_reloader=False, host='0.0.0.0', port=5000)
