"""
Custom behaviour for populating a prompt template with dynamic values.

This module defines the `populate_prompt` class, which allows the system
to replace placeholders within a given prompt string with values retrieved
from the knowledge base or other sources.
"""

import simplejson as json

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class populate_prompt(CustomBehaviour):
    """!@brief Fills a prompt text with key-value replacements.

    This custom behaviour takes a prompt string and a dictionary of replacements.
    It iterates through the replacement dictionary, resolves values from the
    knowledge base if necessary (including handling nested template structures),
    and then replaces corresponding placeholders in the prompt text. The final
    populated prompt is stored in the knowledge base.

    Args:
        prompt_text (str): The base prompt string containing placeholders to be
                           replaced (e.g., "Hello {name}, your query is {query}").
                           Can be a direct string or a knowledge base key.
        replace (dict): A dictionary where keys are the placeholders to find
                        in `prompt_text` (e.g., "{name}", "{query}") and values
                        are either direct strings or knowledge base keys.
                        Values can also be a list `["template {}", ["KB_KEY"]]`
                        for nested replacements.
        output (str, optional): The knowledge base key under which the final
                                populated prompt string will be stored.
                                Defaults to "PROMPT_TEXT".
        success_action (list, optional): An action to execute if the prompt
                                         population is successful.
        failed_action (list, optional): An action to execute if the population
                                        fails.

    Example:
    ["custom", { "name": "populate_prompt",
                 "args": {
                            "prompt_text": "Hello {USER_NAME}, your current task is {CURRENT_TASK}.",
                            "replace": {
                                "{USER_NAME}": "USER_NAME_KB_KEY",
                                "{CURRENT_TASK}": "TASK_DESCRIPTION_KB_KEY"
                            },
                            "output": "FINAL_PROMPT_FOR_LLM"
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the prompt population logic.

        This method retrieves and validates the `prompt_text` and `replace`
        arguments. It then iterates through the `replace` dictionary, resolving
        values from the knowledge base and handling nested template structures.
        Finally, it performs the string replacements in `prompt_text` and
        stores the result in the knowledge base.
        """
        prompt_text = self.parse_simple_input(key="prompt_text", check_for_type="str")

        if prompt_text is None:
            logger.error("populate_prompt: missing or invalid prompt_text(str)")
            await self.failed()
            return

        replace = self.parse_simple_input(key="replace", check_for_type="dict")

        if replace is None:
            logger.error("populate_prompt: missing or invalid replace(dict)")
            await self.failed()
            return

        # Deep copy the replace dictionary to avoid modifying the original details
        replace_resolved = json.loads(json.dumps(self.details["replace"]))
        for k, v in replace_resolved.items():
            if isinstance(v, str) and v in self.kb:
                value = self.kb[v]
                if isinstance(value, list) and len(value) > 1:
                    # Handle nested template: ["content {}", ["key"]]
                    keys = value[1]
                    if not isinstance(keys, list):
                        logger.error(
                            "populate_prompt: invalid replace: invalid composite value format for key '%s'",
                            k,
                        )
                        await self.failed()
                        return
                    content = value[0]
                    for key in keys:
                        if key in self.kb:
                            content = content.replace("{}", str(self.kb[key]), 1)
                        else:
                            _key = str(key).replace("_", " ")
                            content = content.replace("{}", _key, 1)
                    replace_resolved[k] = content
                else:
                    replace_resolved[k] = value
            # If v is not a string or not in kb, it's used as a literal replacement value

        logger.debug("final replacement string %s", replace_resolved)

        for k, v in replace_resolved.items():
            prompt_text = prompt_text.replace(
                k, str(v)
            )  # Ensure replacement value is string

        if "output" in self.details and isinstance(self.details["output"], str):
            self.kb[self.details["output"]] = prompt_text
        else:
            self.kb["PROMPT_TEXT"] = prompt_text
        await self.succeeded()
