from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger
import random


class random_picker(CustomBehaviour):
    """!@brief randomly pick an item from a list
    Example:
    ["custom", { "name": "random_picker",
                 "args": {
                            "list": ["story1", "story2"],
                            "output": "variable_output"
                          }
                }
    ]
    """

    async def run(self):
        data_list = self.parse_simple_input(key="list", check_for_type="list")

        if data_list is None:
            logger.error("random_picker: missing or invalid list(list)")
            await self.failed()
            return

        output = self.parse_simple_input(key="output", check_for_type="str")

        if output is None:
            logger.error("random_picker: missing or invalid output(str)")
            await self.failed()
            return

        self.kb[output] = random.choice(data_list)
        await self.succeeded()
