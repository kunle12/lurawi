from fastapi.responses import StreamingResponse
from lurawi.webhook_handler import WebhookHandler
from lurawi.utils import is_indev, get_dev_stream_handler, set_dev_stream_handler


class GetConversationStream(WebhookHandler):
    def __init__(self, server=None):
        super(GetConversationStream, self).__init__(server)
        self.is_disabled = not is_indev()
        self.route = "/dev/stream"
        self.methods = ["GET"]

    async def process_callback(self):
        stream_handler = get_dev_stream_handler()
        if not stream_handler:
            return self.write_http_response(
                404, {"status": "failed", "message": "No stream data available."}
            )

        set_dev_stream_handler(None)

        headers = {"X-Accel-Buffering": "no"}
        return StreamingResponse(
            stream_handler.stream_generator(),
            headers=headers,
            media_type="text/event-stream",
        )
