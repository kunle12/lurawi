"""
Custom behaviour for dynamically routing and playing selected behaviours.

This module defines the `behaviour_router` class, which allows for the
dynamic selection and execution of other behaviours based on specified
criteria, including random selection or selection from a restricted list.
"""

import random
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class behaviour_router(CustomBehaviour):
    """!@brief Dynamically routes and plays a selected behaviour.

    This custom behaviour enables the dynamic selection and execution of
    other behaviours within the system. It supports random selection from
    all active behaviours or from a predefined, restricted list of behaviours.

    Args:
        select (str): Specifies the selection method. Can be "random" to pick
                      a behaviour randomly, or the exact name of a behaviour
                      to play. If a knowledge base key, its value is used.
        behaviours (list, optional): A list of behaviour names (strings) to
                                     restrict the selection. If provided,
                                     selection will only occur from this list.
                                     Can also be a knowledge base key whose
                                     value is a list.
        restricted (bool, optional): If `True` and `behaviours` is provided,
                                     the `select` argument must be one of the
                                     behaviours in the `behaviours` list.
                                     Defaults to `False`.
        failed_action (list, optional): An action to execute if the behaviour
                                        fails (e.g., `["play_behaviour", "next"]`).

    Example: Randomly select from a restricted list:
    ["custom", { "name": "behaviour_router",
                 "args": {
                            "select": "random",
                            "behaviours": ["story1", "story2", "story3"],
                            "restricted": True,
                            "failed_action": ["play_behaviour", "next"]
                         }
               }
    ]
    """

    def __init__(self, kb, details):
        """
        Initializes the behaviour_router custom behaviour.

        Args:
            kb (dict): The knowledge base dictionary.
            details (dict): A dictionary containing the arguments for this behaviour.
        """
        super().__init__(kb, details)
        # Access the list of all active behaviours from the ActivityManager module
        self.active_behaviours = self.kb["MODULES"]["ActivityManager"].behaviours[
            "behaviours"
        ]

    async def run(self):
        """
        Executes the behaviour_router logic.

        This method parses the 'select', 'behaviours', and 'restricted' arguments
        from the behaviour details, performs the appropriate behaviour selection
        (random or specific), validates the selection against active behaviours
        and restricted lists, and then triggers the selected behaviour.
        """
        if isinstance(self.details, dict) and "select" in self.details:
            selection = self.details["select"]
            behaviours = []
            # Resolve 'select' if it's a knowledge base key
            if isinstance(selection, str) and selection in self.kb:
                selection = self.kb[selection]

            is_restricted = (
                "restricted" in self.details and self.details["restricted"]
            )

            if "behaviours" in self.details:
                behaviours = self.details["behaviours"]
                # Resolve 'behaviours' if it's a knowledge base key
                if isinstance(behaviours, str) and behaviours in self.kb:
                    behaviours = self.kb[behaviours]

                if not isinstance(behaviours, list):
                    logger.error(
                        "behaviour_router: 'behaviours' expected to be a list. Got %s. Aborting",
                        self.details
                    )
                    await self.failed()
                    return

            if is_restricted and not behaviours:
                logger.error(
                    "behaviour_router: 'behaviours' is not defined when restricted is true. Got %s. Aborting",
                    self.details
                )
                await self.failed()
                return

            if selection == "random":
                logger.debug("select a random behaviour")
                if behaviours:
                    # Try to pick a random behaviour from the restricted list that actually exists
                    trials = 0
                    while trials < 10:  # Limit trials to prevent infinite loops
                        selection = random.choice(behaviours)
                        if self._check_if_exists(selection):
                            break
                        else:
                            selection = None
                            trials += 1
                    if not selection:
                        logger.error(
                            "behaviour_router: provided behaviours list is inconsistent with active behaviours. Got %s. Aborting",
                            self.details
                        )
                        await self.failed()
                        return
                else:
                    # Pick a random behaviour from all active behaviours
                    selection = random.choice(self.active_behaviours)["name"]
            elif behaviours and is_restricted and selection not in behaviours:
                # If restricted, the selected behaviour must be in the provided list
                logger.error(
                    "behaviour_router: 'select' behaviour is not in the 'behaviours' list. Got %s. Aborting",
                    self.details
                )
                await self.failed()
                return
            elif not self._check_if_exists(selection):
                # Ensure the selected behaviour actually exists in the active behaviours
                logger.error(
                    "behaviour_router: 'select' behaviour does not exist. Got %s. Aborting",
                    self.details
                )
                await self.failed()
                return

            selected_action = ["play_behaviour", f"{selection}"]
            logger.info("behaviour_router: play selected behaviour %s", selection)
            await self.succeeded(action=selected_action)
        else:
            logger.error(
                "behaviour_router: arg expected to be a dict with keys 'select'. Got %s. Aborting",
                self.details
            )
            await self.failed()

    def _check_if_exists(self, behaviour: str) -> bool:
        """
        Checks if a given behaviour name exists in the list of active behaviours.

        Args:
            behaviour (str): The name of the behaviour to check.

        Returns:
            bool: `True` if the behaviour exists, `False` otherwise.
        """
        for beh in self.active_behaviours:
            if behaviour == beh["name"]:
                return True
        return False
