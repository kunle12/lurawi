from pydantic import BaseModel
from fastapi import Depends
from fastapi.responses import JSONResponse
from .utils import logger


class WebhookHandler(object):
    def __init__(self, server=None):
        self.server = server
        self.route = "/unknown"
        self.methods = ["POST"]
        self.is_disabled = False

    async def process_callback(self, payload: BaseModel):
        logger.warning("base WebhookHandler: missing handler code")
        return self.write_http_response(200, None)

    async def postdata_handler(self, turn_context, data):
        pass

    def write_http_response(self, status, body_dict):
        return JSONResponse(status_code=status, content=body_dict)

    def fini(self):
        pass
