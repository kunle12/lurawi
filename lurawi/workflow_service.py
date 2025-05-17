import os
import importlib
import inspect
import signal

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from .workflow_engine import WorkflowEngine
from .webhook_handler import WebhookHandler
from .utils import logger, is_indev


class WorkflowService(object):
    def __init__(self, custom_behaviour: str):
        self.workflow_engine = WorkflowEngine(custom_behaviour=custom_behaviour)
        self.router = APIRouter()
        self.app = None
        self.webhook_handlers = {}

    def create_app(self) -> FastAPI:
        self.app = FastAPI(
            title="Agent Workflow Runtime Service",
            version="0.0.1",
        )
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.router.add_api_route(
            "/{project}/message",
            endpoint=self.workflow_engine.on_event,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/healthcheck", endpoint=self.workflow_engine.health_check, methods=["GET"]
        )
        if is_indev():
            self.router.add_api_route(
                "/codeupdate",
                endpoint=self.workflow_engine.on_code_update,
                methods=["POST"],
            )
        self._register_webhook_handlers(self.router)
        self.app.add_event_handler("startup", self.handle_signal)
        self.app.include_router(self.router)
        return self.app

    def handle_signal(self):
        default_sigint_handler = signal.getsignal(signal.SIGINT)

        def terminate_now(signum: int, frame):
            # do whatever you need to unblock your own tasks
            for _, handler in self.webhook_handlers.items():
                handler.fini()
            self.workflow_engine.on_shutdown()
            default_sigint_handler(signum, frame)

        signal.signal(signal.SIGINT, terminate_now)

    def _load_webhook_handlers(self):
        if not os.path.exists("lurawi/handlers"):
            return

        for _, _, files in os.walk("lurawi/handlers"):
            for f in files:
                if f.endswith(".py") and f != "__init__.py":
                    mpath = "lurawi.handlers." + os.path.splitext(f)[0]
                    try:
                        m = importlib.import_module(mpath)
                    except Exception as err:
                        logger.error(
                            "Unable to import api handler module %s: %s", f, err
                        )
                        continue
                    for name, objclass in inspect.getmembers(m, inspect.isclass):
                        if (
                            issubclass(objclass, WebhookHandler)
                            and name != "WebhookHandler"
                        ):
                            try:
                                obj = objclass(self.workflow_engine)
                                if not obj.is_disabled:
                                    self.webhook_handlers[obj.route] = obj
                                    logger.info("%s is initialised.", name)
                            except Exception as err:
                                logger.error(
                                    "Unable to webhook handler %s: %s", name, err
                                )

    def _register_webhook_handlers(self, router):
        self._load_webhook_handlers()
        for route, handler in self.webhook_handlers.items():
            router.add_api_route(
                route, endpoint=handler.process_callback, methods=handler.methods
            )
