import re
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class validate_with_regex(CustomBehaviour):
    """!@brief validate input text against regex rules
    Example:
    ["custom", { "name": "validate_with_regex",
                 "args": {
                            "input_text": "input text",
                            "regex": "",
                            "success_action": ["play_behaviour", "next"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    async def run(self):
        input_text = self.parse_simple_input(key="input_text", check_for_type="str")

        if input_text is None:
            logger.error("validate_with_regex: missing or invalid input_text(str)")
            await self.failed()
            return

        regex = self.parse_simple_input(key="regex", check_for_type="str")

        if regex is None:
            logger.error("validate_with_regex: missing or invalid regex(str)")
            await self.failed()
            return

        try:
            regex = re.compile(regex)
        except Exception as err:
            logger.error(f"validate_with_regex: invalid regex: {err}")
            await self.failed()
            return

        if regex.fullmatch(input_text):
            await self.succeeded()
        else:
            await self.failed()
