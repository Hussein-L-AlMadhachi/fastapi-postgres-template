import middleware

from . import index


def attach(app):
    middleware.attach(app)
    app.include_router(index.router)
