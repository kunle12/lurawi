"""
Custom behaviour for caching user-bot conversation history.

This module defines the `cache_conversation_history` class, which is used
to store and manage the dialogue turns between a user and a bot,
optionally enforcing a maximum token limit by purging older entries.
"""

import re
import simplejson as json

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import calc_token_size, logger


class cache_conversation_history(CustomBehaviour):
    """!@brief Caches user-bot conversation history.

    This custom behaviour appends new user input and LLM output to a
    conversation history list. It can also manage the history size by
    truncating older entries if a `max_tokens` limit is specified.

    Args:
        user_input (str): The user's message to be added to the history.
                          If a knowledge base key, its value is used.
        llm_output (str): The LLM's response to be added to the history.
                          If a knowledge base key, its value is used.
        history (list, optional): The existing conversation history list.
                                  If a knowledge base key, its value is used.
                                  Defaults to an empty list if not provided
                                  or if `LLM_CACHED_HISTORY` is not in KB.
        max_tokens (int, optional): The maximum allowed token size for the
                                    entire conversation history. If exceeded,
                                    older entries will be purged. Defaults to -1 (no limit).

    Example:
    ["custom", { "name": "cache_conversation_history",
                 "args": {
                            "user_input": "USER_MESSAGE",
                            "llm_output": "LLM_RESPONSE",
                            "history": ["CONVERSATION_HISTORY_LIST"],
                            "max_tokens": 4000
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the conversation history caching logic.

        This method retrieves user input, LLM output, and existing history,
        then appends the new conversation turn. If a `max_tokens` limit is
        set, it prunes older history entries to stay within the limit.
        The updated history is stored in the knowledge base.
        """
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

        logger.debug("cache_conversation_history: final history list %s", {history})

        if "history" in self.details and isinstance(self.details["history"], str):
            self.kb[self.details["history"]] = history
        else:
            self.kb["LLM_CACHED_HISTORY"] = history

        await self.succeeded()
