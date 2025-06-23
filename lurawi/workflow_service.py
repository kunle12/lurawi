"""
Workflow Service Module for the Lurawi System.

This module provides a FastAPI-based service for managing workflows in the Lurawi system.
It sets up API endpoints for workflow execution, health checks, and webhook handling.

The service automatically discovers and registers webhook handlers from the handlers directory,
and provides graceful shutdown handling through signal management.
"""

import os
import importlib
import inspect
import signal

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from lurawi.workflow_engine import WorkflowEngine
from lurawi.webhook_handler import WebhookHandler
from lurawi.utils import logger, is_indev


class WorkflowService:
    """
    Service class for managing workflow execution and API endpoints.

    This class creates a FastAPI application that exposes endpoints for workflow execution,
    health checks, and webhook handling. It automatically discovers and registers webhook
    handlers from the handlers directory.
    """

    def __init__(self, custom_behaviour: str):
        """
        Initialize a new WorkflowService.

        Args:
            custom_behaviour (str): Path to the custom behaviour module to use

        Note:
            This initializes the workflow engine but does not create the FastAPI app.
            Call create_app() to create and configure the FastAPI application.
        """
        self.workflow_engine = WorkflowEngine(custom_behaviour=custom_behaviour)
        self.router = APIRouter()
        self.app = None
        self.webhook_handlers = {}

    def create_app(self) -> FastAPI:
        """
        Create and configure the FastAPI application.

        This method:
        1. Creates a new FastAPI application
        2. Configures CORS middleware
        3. Adds API routes for workflow events, health checks, and code updates
        4. Registers webhook handlers
        5. Sets up signal handling for graceful shutdown

        Returns:
            FastAPI: The configured FastAPI application
        """
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
        """
        Set up signal handling for graceful shutdown.

        This method is registered as a startup event handler for the FastAPI application.
        It captures SIGINT (Ctrl+C) signals and ensures that all webhook handlers and
        the workflow engine are properly shut down before terminating.

        Returns:
            None
        """
        default_sigint_handler = signal.getsignal(signal.SIGINT)

        def terminate_now(signum: int, frame):
            # do whatever you need to unblock your own tasks
            for _, handler in self.webhook_handlers.items():
                handler.fini()
            self.workflow_engine.on_shutdown()

            # Call the default handler if it's callable
            if callable(default_sigint_handler):
                default_sigint_handler(signum, frame)
            else:
                # If not callable, use the default behaviour (exit)
                os._exit(1)  # Force exit

        signal.signal(signal.SIGINT, terminate_now)

    def _load_webhook_handlers(self):
        """
        Discover and load webhook handlers from the handlers directory.

        This method:
        1. Scans the lurawi/handlers directory for Python files
        2. Imports each file and looks for classes that inherit from WebhookHandler
        3. Instantiates each handler class and adds it to the webhook_handlers dictionary

        Returns:
            None

        Note:
            Handlers with is_disabled=True are not registered
        """
        if not os.path.exists("lurawi/handlers"):
            return

        for _, _, files in os.walk(
            "lurawi/handlers"
        ):  # pylint: disable=too-many-nested-blocks
            for f in files:
                if f.endswith(".py") and f != "__init__.py":
                    mpath = "lurawi.handlers." + os.path.splitext(f)[0]
                    try:
                        m = importlib.import_module(mpath)
                    except Exception as err:  # pylint: disable=broad-exception-caught
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
                            except (
                                Exception  # pylint: disable=broad-exception-caught
                            ) as err:
                                logger.error(
                                    "Unable to webhook handler %s: %s", name, err
                                )

    def _register_webhook_handlers(self, router):
        """
        Register webhook handlers with the API router.

        This method loads webhook handlers using _load_webhook_handlers() and then
        registers each handler's process_callback method as an API endpoint.

        Args:
            router (APIRouter): The FastAPI router to register endpoints with

        Returns:
            None
        """
        self._load_webhook_handlers()
        for route, handler in self.webhook_handlers.items():
            router.add_api_route(
                route, endpoint=handler.process_callback, methods=handler.methods
            )
