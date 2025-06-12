"""
Custom behaviour for retrieving data from a specified URL.

This module defines the `get_data_from_url` class, which allows the system
to make HTTP GET requests to external URLs, optionally including headers
and query parameters, and store the response status and data in the
knowledge base.
"""

from lurawi.utils import aget_data_from_url as get_remote_data, logger
from lurawi.custom_behaviour import CustomBehaviour


class get_data_from_url(CustomBehaviour):
    """!@brief Retrieves data from a specified URL via an HTTP GET request.

    This custom behaviour fetches data from a given URL. It supports
    including custom headers and query parameters in the request. The HTTP
    status code and the retrieved data can be stored in the knowledge base.

    Args:
        url (str): The URL from which to retrieve data. This can be a direct
                   string or a knowledge base key whose value is the URL.
        headers (dict, optional): A dictionary of HTTP headers to include in
                                  the request. Defaults to an empty dictionary.
        params (dict, optional): A dictionary of query parameters to append
                                 to the URL. Defaults to an empty dictionary.
        return_status (str, optional): The knowledge base key under which the
                                       HTTP status code of the response will
                                       be stored.
        return_data (str, optional): The knowledge base key under which the
                                     retrieved data (parsed as JSON if applicable,
                                     otherwise raw text) will be stored.
        success_action (list, optional): An action to execute if the data
                                         retrieval is successful (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if the data
                                        retrieval fails (e.g., `["play_behaviour", "next"]`).

    Example:
    ["custom", { "name": "get_data_from_url",
                 "args": {
                            "url": "http://api.example.com/users",
                            "headers": { "Authorization": "Bearer YOUR_TOKEN" },
                            "params": { "id": "123" },
                            "return_status": "HTTP_STATUS",
                            "return_data": "USER_DATA",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the data retrieval logic.

        This method parses the 'url', 'headers', and 'params' arguments,
        constructs the full URL, makes the asynchronous HTTP GET request,
        and then stores the response status and data in the knowledge base
        based on the 'return_status' and 'return_data' arguments. It handles
        success and failure actions accordingly.
        """
        url = self.parse_simple_input(key="url", check_for_type="str")

        if url is None:
            logger.error("get_data_from_url: missing or invalid url(str)")
            await self.failed()
            return

        params = self.parse_simple_input(key="params", check_for_type="dict")

        urlstr = url
        if params:
            # Append parameters to the URL, handling the first parameter with '?'
            for k, v in params.items():
                urlstr += f"&{k}={v}"
            if "?" not in urlstr:
                urlstr = urlstr.replace("&", "?", 1) # Replace first '&' with '?'

        headers = self.parse_simple_input(key="headers", check_for_type="dict")

        if headers is None:
            headers = {}

        status, data = await get_remote_data(headers=headers, url=urlstr)

        # Store return status if specified
        if (
            status
            and "return_status" in self.details
            and isinstance(self.details["return_status"], str)
        ):
            self.kb[self.details["return_status"]] = status

        # Handle failure based on HTTP status code
        if status is None or status >= 300 or status < 200:
            if data:
                if isinstance(data, str):
                    self.kb["ERROR_MESSAGE"] = data
                elif isinstance(data, dict) and "message" in data:
                    self.kb["ERROR_MESSAGE"] = data["message"]
            await self.failed()
            self.kb["ERROR_MESSAGE"] = "" # Clear error message after handling
        else:
            # Store return data if specified
            if (
                data
                and "return_data" in self.details
                and isinstance(self.details["return_data"], str)
            ):
                self.kb[self.details["return_data"]] = data
            await self.succeeded()
