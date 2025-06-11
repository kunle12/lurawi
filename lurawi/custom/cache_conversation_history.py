import re
import simplejson as json

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import calc_token_size, logger


class cache_conversation_history(CustomBehaviour):
    """!@brief cache user bot conversation history
    Example:
    ["custom", { "name": "cache_conversation_history",
                 "args": {
                            "user_input": "system prompt text",
                            "llm_output": "user prompt text",
                            "history": [],
                            "max_tokens": 5000,
                          }
                }
    ]
    @note only limited parameters are supported in this call
    """

    async def run(self):
        user_input = self.parse_simple_input(key="user_input", check_for_type="str")

        if user_input is None:
            logger.warning(
                "cache_conversation_history: missing or invalid user_input(str), default to empty string."
            )
            user_input = ""

        llm_output = self.parse_simple_input(key="llm_output", check_for_type="str")

        if llm_output is None:
            logger.warning(
                "cache_conversation_history: missing or invalid llm_output(str), default to empty string."
            )
            llm_output = ""

        history = self.parse_simple_input(
            key="history", check_for_type="list", env_name="LLM_CACHED_HISTORY"
        )

        if history is None:
            history = []

        max_tokens = self.parse_simple_input(key="max_tokens", check_for_type="int")

        if max_tokens is None:
            max_tokens = -1

        if user_input and llm_output:
            llm_output = re.sub(
                r"<think>.*?</think>", "", llm_output
            )  # remove think content
            llm_output = llm_output.strip()  # To remove any leading or trailing spaces
            history.extend(
                [
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": llm_output},
                ]
            )
        else:
            logger.warning(
                "cache_conversation_history: missing user input and/or llm output"
            )

        mesg_str = ""

        mesg_str = json.dumps(history)
        if max_tokens > 0:
            mesg_token_size = calc_token_size(mesg_str)
            while history and mesg_token_size > max_tokens:
                history = history[2:]  # gradually purge history
                mesg_str = json.dumps(history)
                mesg_token_size = calc_token_size(mesg_str)

        logger.debug(f"cache_conversation_history: final history list {history}")

        if "history" in self.details and isinstance(self.details["history"], str):
            self.kb[self.details["history"]] = history
        else:
            self.kb["LLM_CACHED_HISTORY"] = history

        await self.succeeded()
