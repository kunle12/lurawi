"""
Custom behaviour for retrieving a value from a list by its index.

This module defines the `get_indexvalue` class, which allows the system
to access an element within a list (stored in the knowledge base) using
a specified index and then store the retrieved value under a new knowledge
base key.
"""

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class get_indexvalue(CustomBehaviour):
    """!@brief Retrieves a value from a list (array) at a specified index.

    This custom behaviour accesses an element from a list (which can be
    a direct list or a knowledge base key pointing to a list) using an
    integer index. The retrieved value is then stored in the knowledge base
    under a designated key.

    Args:
        array (list or str): The list from which to retrieve the value.
                             If a string, it is treated as a knowledge base
                             key pointing to the list.
        index (int or str): The integer index of the element to retrieve.
                            If a string, it is treated as a knowledge base
                            key pointing to an integer index.
        value (str, optional): The knowledge base key under which the
                               retrieved value will be stored. Defaults to
                               "_VALUE_OUTPUT" if not provided.
        success_action (list, optional): An action to execute if the value
                                         is successfully retrieved (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if the retrieval
                                        fails (e.g., `["play_behaviour", "next"]`).

    Example:
    ["custom", { "name": "get_indexvalue",
                 "args": {
                            "array": "LIST_OF_ITEMS",
                            "index" : 0,
                            "value": "FIRST_ITEM",
                            "success_action": ["play_behaviour", "continue_workflow"],
                            "failed_action": ["play_behaviour", "next"]
                        }
                }
    ]
    """

    async def run(self):
        """
        Executes the index-based value retrieval logic.

        This method parses the 'array' and 'index' arguments, resolves them
        from the knowledge base if necessary, performs type and bounds checking,
        and then retrieves the value at the specified index. The result is
        stored in the knowledge base, and success/failure actions are triggered.
        """
        found = None
        if (
            isinstance(self.details, dict)
            and "array" in self.details
            and "index" in self.details
        ):
            array = self.details["array"]
            index = self.details["index"]

            # Resolve 'array' from knowledge base if it's a key
            if array in self.kb:
                array = self.kb[array]

            # Resolve 'index' from knowledge base if it's a key
            if index in self.kb:
                index = self.kb[index]

            # Validate types
            if not isinstance(array, list):
                logger.error("get_indexvalue: 'array' must be a list. Got %s. Aborting.", type(array))
                await self.failed()
                return
            if not isinstance(index, int) or index < 0:
                logger.error("get_indexvalue: 'index' must be a non-negative integer. Got %s. Aborting.", type(index))
                await self.failed()
                return

            # Check if index is within bounds
            if index < len(array):
                found = array[index]

            if found is None:
                logger.warning("get_indexvalue: No value found at index %d in array. Aborting.", index)
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
                "get_indexvalue: Arguments expected to be a dict with keys 'array' and 'index'. Got %s. Aborting",
                self.details
            )
            await self.failed()
