"""
This module defines the GetConversationStream handler for retrieving real-time
conversation data in development mode.
"""
from fastapi.responses import StreamingResponse
from lurawi.webhook_handler import WebhookHandler
from lurawi.utils import is_indev, get_dev_stream_handler, set_dev_stream_handler


class GetConversationStream(WebhookHandler):
    """
    Handles the retrieval of a conversation stream for development purposes.

    This handler provides a GET endpoint to fetch real-time conversation data
    when the application is running in development mode. It ensures that
    only one stream is active at a time by clearing the stream handler after retrieval.
    """

    def __init__(self, server=None):
        super(GetConversationStream, self).__init__(server)
        self.is_disabled = not is_indev()
        self.route = "/dev/stream"
        self.methods = ["GET"]

    async def process_callback(self):
        """
        Processes the callback to provide a streaming response of conversation data.

        If a development stream handler is available, it returns a StreamingResponse
        with the stream generator. Otherwise, it returns a 404 HTTP response.
        The stream handler is reset after the stream is provided.
        """
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
