from ..custom_behaviour import CustomBehaviour
from ..utils import logger
import random


class behaviour_router(CustomBehaviour):
    """!@brief dynamically route and play a selected behaviour
    Example:
    ["custom", { "name": "behaviour_router",
                 "args": {
                            "select": "random|behaviour name",
                            "behaviours":["story1", "story2"],
                            "restricted": True,
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    When optional behaviour list provides a restricted user defined selection choices,
    otherwise, select behaviour comes from the entire active behaviours if restricted is True.
    """

    def __init__(self, kb, details):
        super(behaviour_router, self).__init__(kb, details)
        self.active_behaviours = self.kb["MODULES"]["ActivityManager"].behaviours[
            "behaviours"
        ]

    async def run(self):
        if isinstance(self.details, dict) and "select" in self.details:
            selection = self.details["select"]
            behaviours = []
            if isinstance(selection, str) and selection in self.kb:
                selection = self.kb[selection]

            is_restricted = (
                "restricted" in self.details and self.details["restricted"]
            )

            if "behaviours" in self.details:
                behaviours = self.details["behaviours"]
                if isinstance(behaviours, str) and behaviours in self.kb:
                    behaviours = self.kb[behaviours]

                if not isinstance(behaviours, list):
                    logger.error(
                        f"behaviour_router: 'behaviours' expected to be a list. Got {self.details}. Aborting"
                    )
                    await self.failed()
                    return

            if is_restricted and not behaviours:
                logger.error(
                    f"behaviour_router: 'behaviours' is not defined when restricted is true. Got {self.details}. Aborting"
                )
                await self.failed()
                return

            if selection == "random":
                logger.debug("select a random behaviour")
                if behaviours:
                    trials = 0
                    while trials < 10:
                        selection = random.choice(behaviours)
                        if self._check_if_exists(selection):
                            break
                        else:
                            selection = None
                            trials += 1
                    if not selection:
                        logger.error(
                            f"behaviour_router: provided behaviours list is inconsistent with active behaviours. Got {self.details}. Aborting"
                        )
                        await self.failed()
                        return
                else:
                    selection = random.choice(self.active_behaviours)["name"]
            elif behaviours and is_restricted and selection not in behaviours:
                logger.error(
                    f"behaviour_router: 'select' behaviour is not in the 'behaviours' list. Got {self.details}. Aborting"
                )
                await self.failed()
                return
            elif not self._check_if_exists(selection):
                logger.error(
                    f"behaviour_router: 'select' behaviour does not exist. Got {self.details}. Aborting"
                )
                await self.failed()
                return

            selected_action = ["play_behaviour", f"{selection}"]
            logger.info(f"behaviour_router: play selected behaviour {selection}")
            await self.log_to_cosmos(
                "UserStories", {"story": selection, "state": "start"}
            )
            await self.succeeded(action=selected_action)
        else:
            logger.error(
                f"behaviour_router: arg expected to be a dict with keys 'select'. Got {self.details}. Aborting"
            )
            await self.failed()

    def _check_if_exists(self, behaviour):
        for beh in self.active_behaviours:
            if behaviour == beh["name"]:
                return True
        return False
