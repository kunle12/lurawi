"""
Custom behaviour for checking the existence of a key in a dictionary or knowledge base.

This module defines the `has_keyvalue` class, which allows the system to
verify if a specified key exists within a given dictionary (store) or directly
in the knowledge base. Based on the existence of the key, it triggers
either a 'true_action' or a 'false_action'.
"""

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class has_keyvalue(CustomBehaviour):
    """!@brief Checks for the existence of a key within a store or the knowledge base.

    This custom behaviour determines if a specified key is present in a target
    dictionary (which can be a knowledge base key pointing to a dictionary, or
    the main knowledge base itself). It then executes a `true_action` if the
    key is found, or a `false_action` if it is not found.

    Args:
        store (str, optional): The knowledge base key pointing to the dictionary
                               to search within. If not provided, the main
                               knowledge base (`self.kb`) is used as the store.
        key (str): The key to search for. If a knowledge base key, its value
                   is used as the actual key to search.
        true_action (list): The action to execute if the key is found.
                            (e.g., `["play_behaviour", "2"]`).
        false_action (list): The action to execute if the key is not found.
                             (e.g., `["play_behaviour", "next"]`).

    Example: Check if 'team' exists in 'QUERY_OUTPUT' and branch accordingly:
    ["custom", { "name": "has_keyvalue",
                 "args": {
                            "store": "QUERY_OUTPUT",
                            "key" : "team",
                            "true_action": ["play_behaviour", "team_found_flow"],
                            "false_action": ["play_behaviour", "team_not_found_flow"]
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the key existence check logic.

        This method parses the 'store', 'key', 'true_action', and 'false_action'
        arguments. It resolves the 'store' and 'key' from the knowledge base
        if necessary, performs the existence check, and then triggers the
        appropriate action based on the result.
        """
        found = False
        if (
            isinstance(self.details, dict)
            and "key" in self.details
            and "true_action" in self.details
            and "false_action" in self.details
        ):
            query_key = self.details["key"]
            store_obj = self.kb # Default store is the knowledge base itself

            if "store" in self.details:
                skey = self.details["store"]
                if skey in self.kb:  # If 'store' arg is a key in the knowledge base
                    store_obj = self.kb[skey]
                else:
                    logger.error("has_keyvalue: 'store' key '%s' not found in knowledge base. Aborting.", skey)
                    await self.failed()
                    return

            # Resolve 'query_key' from knowledge base if it's a key
            if query_key in self.kb:
                query_key = self.kb[query_key]

            # Perform the check
            if isinstance(store_obj, dict):
                found = query_key in store_obj
            else:
                # If store_obj is not a dict, check if the query_key itself exists in kb and is not None
                # This handles the case where 'store' is not provided, and we check directly in self.kb
                found = self.kb.get(query_key) is not None

            if found:
                await self.succeeded(action=self.details["true_action"])
            else:
                await self.succeeded(action=self.details["false_action"])
        else:
            logger.error(
                "has_keyvalue: Arguments expected to be a dict with keys 'key', 'true_action' and 'false_action'. Got %s. Aborting",
                self.details
            )
            await self.failed()
