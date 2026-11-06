from . import auth


def attach(app):
    app.add_middleware(auth.AuthMiddleware)
