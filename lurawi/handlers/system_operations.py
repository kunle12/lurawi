"""
This module defines the SystemOperationsHandler for managing system-level
operations via a webhook.
"""

import os
from typing import Dict
from pydantic import BaseModel
from lurawi.webhook_handler import WebhookHandler


class SystemOperationPayload(BaseModel):
    """
    Represents the payload structure for system operation requests.

    Attributes:
        admin_key (str): The administrative access key for authorization.
        command (str): The command to be executed (e.g., "load").
        value (str | Dict, optional): An optional value associated with the command,
                                       which can be a string or a dictionary.
    """

    admin_key: str
    command: str
    value: str | Dict = None


class SystemOperationsHandler(WebhookHandler):
    """
    Handles system-level operations via a webhook endpoint.

    This handler provides an interface for administrative commands, such as
    loading pending behaviours, protected by an admin key. It is disabled
    by default unless explicitly enabled via environment variables.
    """

    def __init__(self, server):
        """
        Initializes the SystemOperationsHandler.

        Args:
            server: The server instance to which this handler is attached.
        """
        super(SystemOperationsHandler, self).__init__(server)
        self.route = "/backend_operation"
        self.is_disabled = (
            "BackendOperationEnabled" not in os.environ
            or os.environ["BackendOperationEnabled"] != "1"
        )

    async def process_callback(
        self, payload: SystemOperationPayload
    ):  # pylint: disable=unused-argument
        """
        Processes incoming system operation requests.

        This method validates the admin key and executes the specified command.
        Currently supports the "load" command to load pending behaviours.

        Args:
            payload (SystemOperationPayload): The incoming request payload
                                              containing the admin key, command, and value.

        Returns:
            HTTP response indicating success or failure with a message.
        """
        if "SystemAdminKey" not in os.environ:
            return self.write_http_response(
                400,
                {
                    "status": "failed",
                    "message": "Missing system admin configuration, this webhook is disabled.",
                },
            )

        if os.environ["SystemAdminKey"] != payload.admin_key:
            return self.write_http_response(
                400, {"status": "failed", "message": "Invalid authorisation."}
            )

        if payload.command == "load":
            behaviour = ""
            if isinstance(payload.value, str):
                behaviour = payload.value
            mesg = self.server.load_pending_behaviours(behaviour)
            return self.write_http_response(200, {"status": "success", "message": mesg})
