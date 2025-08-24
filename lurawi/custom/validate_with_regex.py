"""
Custom behaviour for validating input text against a regular expression.

This module defines the `validate_with_regex` class, which allows the system
to check if a given input string fully matches a specified regular expression
pattern, and then trigger success or failure actions accordingly.
"""

import re
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class validate_with_regex(CustomBehaviour):
    """!@brief Validates input text against a regular expression.

    This custom behaviour takes an input string and a regular expression
    pattern. It attempts to compile the regex and then checks if the input
    string *fully matches* the pattern. Based on the match result, it triggers
    either a `success_action` or a `failed_action`.

    Args:
        input_text (str): The text string to be validated. Can be a direct
                          string or a knowledge base key whose value is the text.
        regex (str): The regular expression pattern to use for validation.
                     Can be a direct string or a knowledge base key whose
                     value is the regex pattern.
        success_action (list, optional): An action to execute if the `input_text`
                                         fully matches the `regex` (e.g., `["play_behaviour", "next"]`).
        failed_action (list, optional): An action to execute if the `input_text`
                                        does not fully match the `regex` or if
                                        the `regex` is invalid (e.g., `["play_behaviour", "next"]`).

    Example: Validate if an input is a valid email format:
    ["custom", { "name": "validate_with_regex",
                 "args": {
                            "input_text": "USER_EMAIL_INPUT",
                            "regex": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+[a-zA-Z]{2,}$",
                            "success_action": ["play_behaviour", "email_valid"],
                            "failed_action": ["play_behaviour", "email_invalid"]
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the regex validation logic.

        This method retrieves and validates the `input_text` and `regex`
        arguments. It attempts to compile the regex pattern and then performs
        a full match against the input text. Success or failure actions are
        triggered based on the match result or any errors during regex compilation.
        """
        input_text = self.parse_simple_input(key="input_text", check_for_type="str")

        if input_text is None:
            logger.error(
                "validate_with_regex: missing or invalid 'input_text' argument (expected a string). Aborting."
            )
            await self.failed()
            return

        regex_pattern = self.parse_simple_input(key="regex", check_for_type="str")

        if regex_pattern is None:
            logger.error(
                "validate_with_regex: missing or invalid 'regex' argument (expected a string). Aborting."
            )
            await self.failed()
            return

        try:
            compiled_regex = re.compile(regex_pattern)
        except Exception as err:
            logger.error(
                "validate_with_regex: invalid regex pattern '%s': %s. Aborting.",
                regex_pattern,
                err,
            )
            self.kb["ERROR_MESSAGE"] = f"Invalid regex pattern: {err}"
            await self.failed()
            self.kb["ERROR_MESSAGE"] = ""
            return

        if compiled_regex.fullmatch(input_text):
            logger.info(
                "validate_with_regex: Input text '%s' fully matches regex pattern.",
                input_text,
            )
            await self.succeeded()
        else:
            logger.info(
                "validate_with_regex: Input text '%s' does NOT fully match regex pattern.",
                input_text,
            )
            await self.failed()
