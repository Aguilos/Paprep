from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    # Monkey-patch only for local dev — gunicorn's gevent worker handles this itself
    try:
        import gevent.monkey
        gevent.monkey.patch_all()
    except ImportError:
        try:
            import eventlet
            eventlet.monkey_patch()
        except Exception:
            pass

    # Use SocketIO runner to support WebSocket connections in development
    # Disable the auto-reloader so monkey-patching happens cleanly in the main process
    socketio.run(app, debug=True, use_reloader=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

