from ..utils import aget_data_from_url as get_remote_data, logger
from ..custom_behaviour import CustomBehaviour


class get_data_from_url(CustomBehaviour):
    """!@brief create an asset request in the asset registry.
    Example:
    ["custom", { "name": "get_data_from_url",
                 "args": {
                            "url": "http://localhost:8090/user/profile",
                            "headers": { "options" : "content" },
                            "params": { "key": "data" },
                            "return_status": "variable to store return status, if any",
                            "return_data": "variable to store return results if any",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    def __init__(self, kb, details):
        super(get_data_from_url, self).__init__(kb, details)

    async def run(self):
        url = self.parse_simple_input(key="url", check_for_type="str")

        if url is None:
            logger.error("get_data_from_url: missing or invalid url(str)")
            await self.failed()
            return

        params = self.parse_simple_input(key="params", check_for_type="dict")

        urlstr = url
        if params:
            for k, v in params.items():
                urlstr += f"&{k}={v}"
            if "?" not in urlstr:
                urlstr.replace("&", "?", 1)

        headers = self.parse_simple_input(key="headers", check_for_type="dict")

        if headers is None:
            headers = {}

        status, data = await get_remote_data(headers=headers, url=urlstr)

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
            await self.succeeded()
