"""
This module defines the RemoteServiceNotificationHandler for processing
notifications from remote services.
"""

import os
from typing import Dict

import requests
from pydantic import BaseModel
from lurawi.webhook_handler import WebhookHandler
from lurawi.utils import is_indev, logger


class RemoteServiceNotificationPayload(BaseModel):
    """
    Represents the payload structure for remote service notifications.

    Attributes:
        success (bool): Indicates if the remote service operation was successful.
        access_key (str): The access key for authorization.
        uid (str): The unique identifier of the user associated with the notification.
        method (str): The method or type of remote service operation.
        data (str | Dict): Method-specific data, can be a string or a dictionary.
    """

    success: bool
    access_key: str
    uid: str
    method: str
    data: str | Dict


class RemoteServiceNotificationHandler(WebhookHandler):
    """
    Handles incoming notifications from remote services.

    This handler sets up a webhook endpoint to receive callbacks from external
    services, processing the payload to update member information or trigger
    specific actions based on the remote service's response. It also dynamically
    determines the callback URL based on the environment.
    """

    def __init__(self, server):
        """
        Initializes the RemoteServiceNotificationHandler.

        Args:
            server: The server instance to which this handler is attached.
        """
        super().__init__(server)
        self.route = "/remote_callback"
        if "RemoteWebhookURL" in os.environ:
            self.server.knowledge["REMOTE_CALLBACK_URL"] = (
                f"{os.environ['RemoteWebhookURL']}/remote_callback"
            )
        else:
            local_ip = "127.0.0.1"
            if not is_indev():
                METADATA_URI = os.environ["ECS_CONTAINER_METADATA_URI"]
                container_metadata = requests.get(METADATA_URI).json()
                local_ip = container_metadata["Networks"][0]["IPv4Addresses"][0]

            logger.info(f"discovering local ip address {local_ip}")
            self.server.knowledge["REMOTE_CALLBACK_URL"] = (
                f"http://{local_ip}:{int(os.getenv('PORT', 8081))}/remote_callback"
            )

    async def process_callback(
        self, payload: RemoteServiceNotificationPayload
    ):  # pylint: disable=unused-argument
        """Process incoming data is expected to have the following format:
        {
            "access_key": "fjeoijoefvjae", # access key put as the same as activity id
            "uid": "220", # for which user
            "method": "guardrails_validator"
            "data" : Dict # method specific data
        }
        """

        member = self.server.get_member(uid=payload.uid)
        if not member:
            return self.write_http_response(
                400,
                {
                    "status": "failed",
                    "message": f"Unknown uid {payload.uid} for remote callback.",
                },
            )

        if not member.check_remote_callback_access(payload.access_key):
            return self.write_http_response(
                400,
                {
                    "status": "failed",
                    "message": "Invalid authorisation for remote callback.",
                },
            )

        if payload.success:
            await member.process_remote_callback_payload(
                method=payload.method, data=payload.data
            )

        return self.write_http_response(200, {"status": "success"})
