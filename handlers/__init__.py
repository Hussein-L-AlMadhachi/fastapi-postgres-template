import middleware

from handlers import auth, index, users


def attach(app):
    middleware.attach(app)
    app.include_router(index.router)
    app.include_router(auth.router)
    app.include_router(users.router)
