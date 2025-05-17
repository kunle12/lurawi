import os
from pydantic import BaseModel, Extra
from typing import Dict
from ..webhook_handler import WebhookHandler


class SystemOperationPayload(BaseModel):
    admin_key: str
    command: str
    value: str | Dict = None


class SystemOperationsHandler(WebhookHandler):
    def __init__(self, server):
        super(SystemOperationsHandler, self).__init__(server)
        self.route = "/backend_operation"
        self.is_disabled = (
            "BackendOperationEnabled" not in os.environ
            or os.environ["BackendOperationEnabled"] != "1"
        )

    async def process_callback(
        self, payload: SystemOperationPayload
    ):  # pylint: disable=unused-argument
        """Process incoming data is expected to have the following format:
        {
            "admin_key": "fjeoijoefvjae", # admin access key
        }
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
