"""
Module for handling incoming webhooks and processing their payloads.

This module defines the `WebhookHandler` class, which serves as a base for
creating custom webhook handlers within the Lurawi system. It provides
methods for initializing the handler, processing incoming data, and
generating HTTP responses.
"""

from pydantic import BaseModel
from fastapi.responses import JSONResponse
from lurawi.utils import logger


class WebhookHandler:
    """
    Base class for handling incoming webhooks.

    Provides a structure for defining webhook routes, HTTP methods,
    and methods for processing incoming payloads and generating responses.
    Custom webhook handlers should inherit from this class and override
    the `process_callback` method.
    """

    def __init__(self, server=None):
        """
        Initializes the WebhookHandler.

        Args:
            server: The server instance to which this webhook handler is attached.
                    Defaults to None.
        """
        self.server = server
        self.route = "/unknown"
        self.methods = ["POST"]
        self.is_disabled = False

    async def process_callback(self, payload: BaseModel):
        """
        Processes the incoming webhook payload.

        This method should be overridden by subclasses to implement specific
        webhook handling logic.

        Args:
            payload (BaseModel): The incoming payload, validated by Pydantic.

        Returns:
            JSONResponse: An HTTP response indicating the status of the processing.
        """
        logger.warning("base WebhookHandler: missing handler code")
        return self.write_http_response(200, None)

    async def postdata_handler(self, turn_context, data):
        """
        Handles post-data processing for the webhook.

        This method is intended to be overridden by subclasses for additional
        processing after the initial callback.

        Args:
            turn_context: The context of the current turn.
            data: The data associated with the post-data event.
        """

    def write_http_response(self, status: int, body_dict: dict):
        """
        Creates a FastAPI JSONResponse.

        Args:
            status (int): The HTTP status code for the response.
            body_dict (dict): The dictionary to be used as the JSON content of the response.

        Returns:
            JSONResponse: A FastAPI JSONResponse object.
        """
        return JSONResponse(status_code=status, content=body_dict)

    def fini(self):
        """
        Performs any necessary cleanup when the webhook handler is finalized.

        This method is intended to be overridden by subclasses for resource cleanup.
        """
