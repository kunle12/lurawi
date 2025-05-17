from ..custom_behaviour import CustomBehaviour
from ..utils import logger


class get_indexvalue(CustomBehaviour):
    """!@brief retrieve value from store[key] and put into value
    Example:
    ["custom", { "name": "get_indexvalue",
                 "args": {
                            "array": "QUERY_OUTPUT",
                            "index" : 0,
                            "value": "KNOWN_TEAM",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note success_action and failed_action are optional.
    """

    def __init__(self, kb, details):
        super(get_indexvalue, self).__init__(kb, details)

    async def run(self):
        found = None
        if (
            isinstance(self.details, dict)
            and "array" in self.details
            and "index" in self.details
        ):
            array = self.details["array"]
            index = self.details["index"]
            if array in self.kb:  # arg is a key in the knowledge
                array = self.kb[array]

            if index in self.kb:
                index = self.kb[index]

            if not isinstance(array, list):
                logger.error("get_indexvalue: array must be a list")
                await self.failed()
            if not isinstance(index, int) or index < 0:
                logger.error("get_indexvalue: index must be a non negative integer.")
                await self.failed()

            if index < len(array):
                found = array[index]

            if found is None:
                await self.failed()
            else:
                if "value" in self.details and isinstance(self.details["value"], str):
                    self.kb[self.details["value"]] = found
                else:
                    self.kb["_VALUE_OUTPUT"] = found
                await self.succeeded()
        else:
            logger.error(
                f"get_indexvalue: arg expected to be a dict with keys 'array', 'index'. Got {self.details}. Aborting"
            )
            await self.failed()
