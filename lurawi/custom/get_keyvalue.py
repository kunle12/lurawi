"""
Custom behaviour for retrieving a value from a dictionary (store) by its key.

This module defines the `get_keyvalue` class, which allows the system to
access an element within a dictionary (stored in the knowledge base or
directly provided) using a specified key and then store the retrieved value
under a new knowledge base key.
"""

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class get_keyvalue(CustomBehaviour):
    """!@brief Retrieves a value from a dictionary (store) using a specified key.

    This custom behaviour fetches a value from a dictionary-like structure.
    The 'store' can be a knowledge base key pointing to a dictionary, or if
    omitted, the main knowledge base itself is used as the store. The 'key'
    can also be resolved from the knowledge base. The retrieved value is then
    stored in the knowledge base under a designated output key.

    Args:
        store (str, optional): The knowledge base key pointing to the dictionary
                               from which to retrieve the value. If not provided,
                               the main knowledge base (`self.kb`) is used as the store.
        key (str): The key whose associated value is to be retrieved from the store.
                   If a knowledge base key, its value is used as the actual key.
        value (str, optional): The knowledge base key under which the retrieved
                               value will be stored. Defaults to "_VALUE_OUTPUT"
                               if not provided.
        success_action (list, optional): An action to execute if the value is
                                         successfully retrieved (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if the retrieval
                                        fails (e.g., `["play_behaviour", "next"]`).

    Example: Retrieve 'team' from 'QUERY_OUTPUT' and store it as 'KNOWN_TEAM':
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
    """

    async def run(self):
        """
        Executes the key-value retrieval logic.

        This method parses the 'store' and 'key' arguments, resolves them
        from the knowledge base if necessary, and attempts to retrieve the
        value. The result is stored in the knowledge base, and success/failure
        actions are triggered.
        """
        found = None
        if isinstance(self.details, dict) and "key" in self.details:
            query_key = self.details["key"]
            store_obj = self.kb # Default store is the knowledge base itself

            if "store" in self.details:
                skey = self.details["store"]
                if skey in self.kb:  # If 'store' arg is a key in the knowledge base
                    store_obj = self.kb[skey]
                else:
                    logger.error("get_keyvalue: 'store' key '%s' not found in knowledge base. Aborting.", skey)
                    await self.failed()
                    return

            # Resolve 'query_key' from knowledge base if it's a key
            if query_key in self.kb:
                query_key = self.kb[query_key]

            # Attempt to find the value in the resolved store_obj
            if isinstance(store_obj, dict) and query_key in store_obj:
                found = store_obj[query_key]
            elif not isinstance(store_obj, dict):
                logger.error("get_keyvalue: 'store' must be a dictionary. Got %s. Aborting.", type(store_obj))
                await self.failed()
                return

            if found is None:
                logger.warning("get_keyvalue: Key '%s' not found in the specified store. Aborting.", query_key)
                await self.failed()
            else:
                # Store the found value in the knowledge base
                if "value" in self.details and isinstance(self.details["value"], str):
                    self.kb[self.details["value"]] = found
                else:
                    self.kb["_VALUE_OUTPUT"] = found # Default output key
                await self.succeeded()
        else:
            logger.error(
                "get_keyvalue: Arguments expected to be a dict with at least 'store' and 'key'. Got %s. Aborting",
                self.details
            )
            await self.failed()
