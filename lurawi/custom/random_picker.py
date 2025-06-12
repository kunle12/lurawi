"""
Custom behaviour for randomly selecting an item from a list.

This module defines the `random_picker` class, which allows the system
to pick a random element from a given list (which can be a direct list
or a knowledge base key pointing to a list) and store the selected item
under a new knowledge base key.
"""

import random
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class random_picker(CustomBehaviour):
    """!@brief Randomly picks an item from a list.

    This custom behaviour selects a random element from a provided list.
    The list can be directly specified or referenced via a knowledge base key.
    The selected item is then stored in the knowledge base under a designated
    output key.

    Args:
        list (list or str): The list from which to pick a random item.
                            If a string, it is treated as a knowledge base
                            key pointing to the list.
        output (str): The knowledge base key under which the randomly
                      selected item will be stored.

    Example:
    ["custom", { "name": "random_picker",
                 "args": {
                            "list": ["option_A", "option_B", "option_C"],
                            "output": "SELECTED_OPTION"
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the random item selection logic.

        This method retrieves and validates the 'list' and 'output' arguments.
        It then selects a random item from the resolved list and stores it
        in the knowledge base under the specified output key.
        """
        data_list = self.parse_simple_input(key="list", check_for_type="list")

        if data_list is None:
            logger.error("random_picker: missing or invalid 'list' argument (expected a list). Aborting.")
            await self.failed()
            return

        if not data_list:
            logger.warning("random_picker: provided list is empty. No item to pick. Aborting.")
            await self.failed()
            return

        output = self.parse_simple_input(key="output", check_for_type="str")

        if output is None:
            logger.error("random_picker: missing or invalid 'output' argument (expected a string). Aborting.")
            await self.failed()
            return

        self.kb[output] = random.choice(data_list)
        logger.debug("random_picker: picked '%s' from list. Stored in '%s'.", self.kb[output], output)
        await self.succeeded()
