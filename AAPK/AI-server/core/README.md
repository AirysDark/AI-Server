# AI Server core

`server_impl.py` contains the compatibility implementation extracted from the original `server.py`.

The root `server.py` remains the stable entry point used by local execution and PythonAnywhere WSGI.

This first modular boundary deliberately preserves all existing request behavior while moving the implementation out of the root entry point. Further domain modules can now be extracted without changing the public server import.
