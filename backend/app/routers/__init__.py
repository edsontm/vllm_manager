from app.routers.auth import router as auth_router
from app.routers.instances import router as instances_router
from app.routers.metrics import router as metrics_router
from app.routers.models import router as models_router
from app.routers.policies import router as policies_router
from app.routers.proxy import router as proxy_router
from app.routers.queue import router as queue_router
from app.routers.tokens import router as tokens_router
from app.routers.users import router as users_router

__all__ = [
    "auth_router",
    "users_router",
    "tokens_router",
    "instances_router",
    "metrics_router",
    "queue_router",
    "proxy_router",
    "models_router",
    "policies_router",
]
