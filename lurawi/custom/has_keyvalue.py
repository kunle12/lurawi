from ..custom_behaviour import CustomBehaviour
from ..utils import logger


class has_keyvalue(CustomBehaviour):
    """!@brief retrieve value from store[key] and put into value
    Example:
    ["custom", { "name": "has_keyvalue",
                 "args": {
                            "store": "QUERY_OUTPUT",
                            "key" : "team",
                            "true_action": ["play_behaviour", "2"],
                            "false_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note if store is not defined, the base of knowledge is used.
    """

    def __init__(self, kb, details):
        super(has_keyvalue, self).__init__(kb, details)

    async def run(self):
        found = False
        if (
            isinstance(self.details, dict)
            and "key" in self.details
            and "true_action" in self.details
            and "false_action" in self.details
        ):
            query_key = self.details["key"]
            if "store" in self.details:
                skey = self.details["store"]
                if skey in self.kb:  # arg is a key in the knowledge
                    store = self.kb[skey]
                    if query_key in self.kb:
                        query_key = self.kb[query_key]
                    if isinstance(store, dict) and query_key in store:
                        found = True
            elif query_key in self.kb:
                found = self.kb[query_key] is not None

            if found:
                await self.succeeded(action=self.details["true_action"])
            else:
                await self.succeeded(action=self.details["false_action"])
        else:
            logger.error(
                f"has_keyvalue: arg expected to be a dict with keys 'store', 'key', 'true_action' and 'false_action'. Got {self.details}. Aborting"
            )
            await self.failed()
