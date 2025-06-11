from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class get_keyvalue(CustomBehaviour):
    """!@brief retrieve value from store[key] and put into value
    Example:
    ["custom", { "name": "get_keyvalue",
                 "args": {
                            "store": "QUERY_OUTPUT",
                            "key" : "team",
                            "value": "KNOWN_TEAM",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note success_action and failed_action are optional. If store is not defined, the base of knowledge is used.
    """

    async def run(self):
        found = None
        if isinstance(self.details, dict) and "key" in self.details:
            query_key = self.details["key"]
            if "store" in self.details:
                skey = self.details["store"]
                if skey in self.kb:  # arg is a key in the knowledge
                    store = self.kb[skey]
                    if query_key in self.kb:
                        query_key = self.kb[query_key]
                    if isinstance(store, dict) and query_key in store:
                        found = store[query_key]
            elif query_key in self.kb:
                found = self.kb[query_key]

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
                "get_keyvalue: arg expected to be a dict with keys 'store', 'key'. Got %s. Aborting",
                self.details
            )
            await self.failed()
