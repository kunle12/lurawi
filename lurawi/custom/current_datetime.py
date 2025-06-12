"""Custom behaviour to get and format the current datetime."""

from datetime import datetime
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class current_datetime(CustomBehaviour):
    """!@brief Get the current datetime string and save it under a specified knowledge key.

    This custom behaviour retrieves the current datetime, formats it based on the
    'format' argument (or uses a default format), and saves the resulting string
    to the knowledge base under the key specified by the 'output' argument (or
    'CURRENT_DATETIME' by default).

    Example:
    ["custom", { "name": "current_datetime",
                 "args": {
                        "format": "%Y-%m-%d %H:%M:%S",
                        "output": "MY_CUSTOM_DATETIME_KEY"
                    }
                }
    ]
    """

    async def run(self):
        current_time = datetime.now()
        output_time_string = ""

        if "format" in self.details and isinstance(self.details["format"], str):
            try:
                output_time_string = current_time.strftime(self.details["format"])
            except Exception as _:
                output_time_string = current_time.strftime("%d/%m/%Y %H:%M:%S")
        else:
            output_time_string = current_time.strftime("%d/%m/%Y %H:%M:%S")

        if "output" in self.details and isinstance(self.details["output"], str):
            self.kb[self.details["output"]] = output_time_string
        else:
            self.kb["CURRENT_DATETIME"] = output_time_string

        logger.debug("current_datetime: %s", output_time_string)

        await self.succeeded()
