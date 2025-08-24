from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class discord_message(CustomBehaviour):
    """!@brief a function template that takes in a list of items and output a string.
    Example:
    ["custom", { "name": "discord_message",
                 "args": {
                            "user": "discord_user_name_1",
                            "message": "message to be send to users",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    def __init__(self, kb, details):
        super().__init__(kb, details)
        self._discord_service = kb["LURAWI_SYSTEM_SERVICES"].get("DiscordMessenger")

    async def run(self):
        if not self._discord_service:
            logger.error("discord_message: discord service is not available")
            await self.failed()
            return

        user = self.parse_simple_input(key="user", check_for_type="str")

        if user is None:
            logger.error(
                "discord_message: 'user' expected to be a string. Got %s. Aborting",
                self.details,
            )
            await self.failed()
            return

        message = self.parse_simple_input(key="message", check_for_type="str")

        if message is None:
            logger.error(
                "discord_message: 'message' (str) must be a variable name Got %s. Aborting",
                self.details,
            )
            await self.failed()
            return

        if self._discord_service.send_message_to_user(user=user, message=message):
            await self.succeeded()
        else:
            await self.failed()
