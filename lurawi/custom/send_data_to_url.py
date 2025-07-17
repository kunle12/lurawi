"""
Custom behaviour for sending data (payload) to a specified URL via HTTP POST or PUT.

This module defines the `send_data_to_url` class, which allows the system
to make HTTP requests (POST by default, or PUT if specified) to external URLs,
including custom headers and a JSON payload, and store the response status
and data in the knowledge base.
"""

import simplejson as json
from lurawi.utils import apost_payload_to_url, logger
from lurawi.custom_behaviour import CustomBehaviour


class send_data_to_url(CustomBehaviour):
    """!@brief Sends a JSON payload to a specified URL via HTTP POST or PUT.

    This custom behaviour sends data to a given URL using either an HTTP POST
    or PUT request. It supports including custom headers and a JSON payload.
    The HTTP status code and the response data can be stored in the knowledge base.

    Args:
        url (str): The target URL to which the data will be sent.
                   Can be a direct string or a knowledge base key.
        headers (dict, optional): A dictionary of HTTP headers to include in
                                  the request. Defaults to `{"Content-Type": "application/json"}`.
                                  Can be a direct dictionary or a knowledge base key.
        payload (dict): The JSON payload to be sent in the request body.
                        Values within the dictionary can be knowledge base keys
                        or nested template structures `["template {}", ["KB_KEY"]]`.
        use_put (bool, optional): If `True`, an HTTP PUT request is used instead
                                  of POST. Defaults to `False`.
        return_status (str, optional): The knowledge base key under which the
                                       HTTP status code of the response will
                                       be stored.
        return_data (str, optional): The knowledge base key under which the
                                     response data (parsed as JSON if applicable,
                                     otherwise raw text) will be stored. Defaults
                                     to "SENT_DATA_TO_URL_RETURN".
        success_action (list, optional): An action to execute if the data
                                         is successfully sent (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if sending the
                                        data fails (e.g., `["play_behaviour", "next"]`).

    Example:
    ["custom", { "name": "send_data_to_url",
                 "args": {
                            "url" : "https://api.example.com/create_record",
                            "headers": { "Authorization" : "Bearer TOKEN_KB_KEY" },
                            "payload": { "name": "USER_NAME_KB_KEY", "email": "USER_EMAIL_KB_KEY" },
                            "use_put": False,
                            "return_status": "API_RESPONSE_STATUS",
                            "return_data": "API_RESPONSE_DATA",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the data sending logic.

        This method retrieves and validates the URL, payload, headers, and
        `use_put` flag. It resolves payload and header values from the
        knowledge base, makes the asynchronous HTTP request (POST or PUT),
        and then stores the response status and data in the knowledge base.
        It handles success and failure actions accordingly.
        """
        url = self.parse_simple_input(key="url", check_for_type="str")

        if url is None:
            logger.error(
                "send_data_to_url: missing or invalid 'url' argument (expected a string). Aborting."
            )
            await self.failed()
            return

        # TODO: Add more robust URL format validation if necessary

        payload = self.parse_simple_input(key="payload", check_for_type="dict")

        if payload is None:
            logger.error(
                "send_data_to_url: missing or invalid 'payload' argument (expected a dictionary). Aborting."
            )
            await self.failed()
            return

        # Deep copy the payload to avoid modifying the original details
        payload_resolved = json.loads(json.dumps(payload))
        for k, v in payload_resolved.items():
            if isinstance(v, str) and v in self.kb:
                value = self.kb[v]
                if isinstance(value, list) and len(value) > 1:
                    # Handle nested template: ["content {}", ["key"]]
                    keys = value[1]
                    if not isinstance(keys, list):
                        logger.error(
                            "send_data_to_url: invalid payload: invalid composite value format for key '%s'",
                            k,
                        )
                        await self.failed()
                        return
                    content = value[0]
                    for key in keys:
                        if key in self.kb:
                            content = content.replace("{}", str(self.kb[key]), 1)
                        else:
                            _key = str(key).replace("_", " ")
                            content = content.replace("{}", _key, 1)
                    payload_resolved[k] = content
                else:
                    payload_resolved[k] = value
            # If v is not a string or not in kb, it's used as a literal value

        logger.debug("final payload to send %s", payload_resolved)

        headers = {"Content-Type": "application/json"}  # Default headers
        if "headers" in self.details:
            input_headers = self.details["headers"]
            if isinstance(input_headers, str) and input_headers in self.kb:
                input_headers = self.kb[input_headers]

            if not isinstance(input_headers, dict):
                logger.error(
                    "send_data_to_url: invalid 'headers' argument (expected a dictionary). Aborting."
                )
                await self.failed()
                return

            # Resolve header values from KB if they are keys
            for k, v in input_headers.items():
                if isinstance(v, str) and v in self.kb:
                    headers[k] = self.kb[v]
                else:
                    headers[k] = v

            if "Content-Type" not in headers:
                headers["Content-Type"] = (
                    "application/json"  # Ensure default content type if not overridden
                )

        use_put = self.parse_simple_input(key="use_put", check_for_type="bool")

        if use_put is None:
            use_put = False

        status, data = await apost_payload_to_url(
            headers=headers, url=url, payload=payload_resolved, use_put=use_put
        )

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
            logger.error(
                "send_data_to_url: Failed to send data. Status: %s, Data: %s",
                status,
                data,
            )
            await self.failed()
            self.kb["ERROR_MESSAGE"] = ""  # Clear error message after handling
        else:
            # Store return data if specified, or use default key
            if (
                data
                and "return_data" in self.details
                and isinstance(self.details["return_data"], str)
            ):
                self.kb[self.details["return_data"]] = data
            else:
                self.kb["SENT_DATA_TO_URL_RETURN"] = data
            logger.info("send_data_to_url: Data sent successfully. Status: %s", status)
            await self.succeeded()
