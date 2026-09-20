"""
extensions.py
-------------
Flask extension instances that need to be shared between app.py and
blueprint modules (auth.py) without those modules importing each other
directly. app.py creates the real Limiter and calls limiter.init_app(app);
auth.py imports this same `limiter` object to decorate its own routes.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
