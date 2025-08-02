"""
Custom behaviour for handling user text input.

This module defines the `text_input` class, which allows the system to
prompt the user for text input and store the received response in the
knowledge base.
"""

from typing import Dict
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class text_input(CustomBehaviour):
    """!@brief Processes prompted user text inputs.

    This custom behaviour prompts the user for text input and stores the
    received text in the knowledge base under a specified key. It can
    construct dynamic prompts using knowledge base values.

    Args:
        prompt (str or list, optional): The message to display to the user
                                        when requesting input.
                                        - If a string, it's the direct prompt text.
                                        - If a list `["template {}", ["KB_KEY"]]`,
                                          it's a template string with placeholders
                                          `{}` and a list of knowledge base keys
                                          whose values will replace the placeholders.
                                        Defaults to an empty string (no prompt).
        output (str): The knowledge base key under which the user's text
                      input will be stored.

    Example: Using a dynamic prompt:
    ["custom", { "name": "text_input",
                 "args": {
                            "prompt":["Hello {}, what is your favorite color?", ["GUESTNAME"]],
                            "output":"FAVORITE_COLOR"
                          }
                }
    ]
    """

    def __init__(self, kb, details):
        """
        Initializes the text_input custom behaviour.

        Args:
            kb (dict): The knowledge base dictionary.
            details (dict): A dictionary containing the arguments for this behaviour.
        """
        super().__init__(kb, details)
        self.data_key: str | None = None  # Key to store the user's input

    async def run(self):
        """
        Executes the text input prompting logic.

        This method retrieves and validates the 'output' key. It then constructs
        the prompt message (resolving placeholders from the knowledge base if
        the prompt is a template), registers for user message updates, and sends
        the prompt to the user.
        """
        prompt = ""

        self.data_key = self.details.get("output")

        if not self.data_key or not isinstance(self.data_key, str):
            logger.error(
                "text_input: missing or invalid 'output' argument (expected a string). Aborting."
            )
            await self.failed()
            return

        if "prompt" in self.details:
            prompt_arg = self.details["prompt"]
            if isinstance(prompt_arg, list) and len(prompt_arg) == 2:
                # Handle template prompt: ["template {}", ["KB_KEY"]]
                to_say, keys = prompt_arg
                if isinstance(keys, list):
                    for key in keys:
                        if key in self.kb:
                            to_say = to_say.replace("{}", str(self.kb[key]), 1)
                        else:
                            _key = str(key).replace("_", " ")
                            to_say = to_say.replace("{}", _key, 1)
                    prompt = to_say
                else:
                    sample = ["hello {}, good {}", ["KB_KEY1", "KB_KEY2"]]
                    logger.error(
                        "text_input: Invalid prompt format %s. Expected format: %s",
                        prompt_arg,
                        sample,
                    )
                    prompt = ""
            elif isinstance(prompt_arg, str):
                prompt = prompt_arg
            else:
                logger.error(
                    "text_input: Invalid prompt type %s. Expected string or list.",
                    type(prompt_arg),
                )
                prompt = ""

        self.register_for_user_message_updates()  # Register to receive the user's response

        if prompt:
            await self.message(data={"response": prompt})  # Send the prompt to the user

    async def on_user_message_update(self, context: Dict):
        """
        Callback method invoked when a user message update is received.

        This method is triggered after the `text_input` behaviour has prompted
        the user and is awaiting a response. It extracts the user's message
        content and stores it in the knowledge base under the `data_key`.

        Args:
            context (Dict): The user message data context, typically containing
                            `activity.content` with the user's text.
        """
        if "message" in context:
            result = context["message"].strip()
            self.kb[self.data_key] = result
            logger.debug(
                "text_input: User input received and stored in '%s': %s",
                self.data_key,
                result,
            )
            await self.succeeded()
        else:
            logger.error("text_input: data_key was not set, cannot store user input.")
            await self.failed()
