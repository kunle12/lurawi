from lurawi.custom_behaviour import CustomBehaviour
from datetime import datetime
from lurawi.utils import logger


class current_datetime(CustomBehaviour):
    """!@brief get the current date time string: morning, afternoon or evening.
    and save the string under knowledge['CURRENT_DAYTIME']
    Example:
    ["custom", { "name": "current_datetime",
                 "args": {
                        "format": "datetime string format",
                        "output": "output time string"
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

        logger.debug(f"current_datetime: {output_time_string}")

        await self.succeeded()
