from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.internal import router as internal_router
from app.api.routes.reminders import router as reminders_router
from app.api.routes.slack import router as slack_router
from app.api.routes.tasks import router as tasks_router

app = FastAPI(title="todo-platform")
app.include_router(tasks_router)
app.include_router(slack_router)
app.include_router(reminders_router)
app.include_router(internal_router)
app.include_router(auth_router)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
