import os
import requests
from pydantic import BaseModel, Extra
from typing import Dict
from ..webhook_handler import WebhookHandler
from ..utils import is_indev, logger


class RemoteServiceNotificationPayload(BaseModel):
    success: bool
    access_key: str
    uid: str
    method: str
    data: str | Dict


class RemoteServiceNotificationHandler(WebhookHandler):
    def __init__(self, server):
        super(RemoteServiceNotificationHandler, self).__init__(server)
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
