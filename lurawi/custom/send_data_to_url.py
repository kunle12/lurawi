import simplejson as json
from lurawi.utils import apost_payload_to_url, logger
from lurawi.custom_behaviour import CustomBehaviour


class send_data_to_url(CustomBehaviour):
    """!@brief create an asset request in the asset registry.
    Example:
    ["custom", { "name": "send_data_to_url",
                 "args": {
                            "url" : "https://localhost:4848/newuser",
                            "headers": { "Content-Type" : "application/json" },
                            "payload": { "key": "some data" },
                            "use_put": False,
                            "return_status": "variable to store return status, if any",
                            "return_data": "variable to store return results if any",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note this custom provide a generic call to a specific url to post data
    """

    async def run(self):
        url = self.parse_simple_input(key="url", check_for_type="str")

        if url is None:
            logger.error("send_data_to_url: missing or invalid url(str)")
            await self.failed()
            return

        # TODO check url format

        payload = self.parse_simple_input(key="payload", check_for_type="dict")

        if payload is None:
            logger.error("send_data_to_url: missing or invalid payload(dict)")
            await self.failed()
            return

        payload = json.loads(json.dumps(payload))
        for k, v in payload.items():
            if v in self.kb:
                value = self.kb[v]
                if isinstance(value, list) and len(value) > 1:
                    keys = value[1]
                    if not isinstance(keys, list):
                        logger.error(
                            "send_data_to_url: invalid payload: invalid composite value format"
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
                    payload[k] = content
                else:
                    payload[k] = value

        logger.debug(f"final payload to send {payload}")

        headers = {"Content-Type": "application/json"}
        if "headers" in self.details:
            headers = self.details["headers"]
            if isinstance(headers, str) and headers in self.kb:
                headers = self.kb[self.details["headers"]]

            if not isinstance(headers, dict):
                logger.error("send_data_to_url: invalid headers, must be a dict")
                await self.failed()
                return

            for k, v in headers.items():
                if v in self.kb:
                    headers[k] = self.kb[v]

            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

        use_put = self.parse_simple_input(key="use_put", check_for_type="bool")

        if use_put is None:
            use_put = False

        status, data = await apost_payload_to_url(
            headers=headers, url=url, payload=payload, usePut=use_put
        )
        if (
            status
            and "return_status" in self.details
            and isinstance(self.details["return_status"], str)
        ):
            self.kb[self.details["return_status"]] = status
        if status is None or status >= 300 or status < 200:
            if data:
                if isinstance(data, str):
                    self.kb["ERROR_MESSAGE"] = data
                elif isinstance(data, dict) and "message" in data:
                    self.kb["ERROR_MESSAGE"] = data["message"]
            await self.failed()
            self.kb["ERROR_MESSAGE"] = ""
        else:
            if (
                data
                and "return_data" in self.details
                and isinstance(self.details["return_data"], str)
            ):
                self.kb[self.details["return_data"]] = data
            else:
                self.kb["SENT_DATA_TO_URL_RETURN"] = data
            await self.succeeded()
