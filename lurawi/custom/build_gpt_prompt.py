"""
Custom behaviour for constructing prompts for GPT-style models.

This module defines the `build_gpt_prompt` class, which facilitates the
creation of structured prompts by combining system instructions, user queries,
conversation history, and relevant documents, while managing token limits.
"""

from lurawi.utils import cut_string, calc_token_size, logger
from lurawi.custom_behaviour import CustomBehaviour


class build_gpt_prompt(CustomBehaviour):
    """!@brief Builds a custom prompt for GPT-style models.

    This custom behaviour constructs a prompt for large language models by
    integrating a system prompt, a user prompt (which can include a query
    and documents), conversation history, and managing the total token size
    to stay within specified limits.

    Args:
        system_prompt (str, optional): The initial system-level instructions
                                       for the LLM. Defaults to an empty string.
        user_prompt (str, optional): The user's query or prompt template.
                                     Can contain placeholders like `{query}`
                                     and `{docs}`. Defaults to an empty string.
        query (str, optional): The actual user query text to be inserted into
                               the `user_prompt` (replaces `{query}`).
                               Defaults to an empty string.
        history (list, optional): A list of dictionaries representing past
                                  conversation turns (e.g., `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]`).
                                  Defaults to an empty list.
        media_content (list, optional): A list of media content items to be
                                        included with the user prompt.
                                        Defaults to an empty list.
        documents (str, optional): Relevant search results or documents to be
                                   inserted into the `user_prompt` (replaces `{docs}`).
                                   Defaults to an empty string.
        max_tokens (int, optional): The maximum allowed token size for the
                                    entire constructed prompt. If exceeded,
                                    history and documents will be truncated.
                                    Defaults to -1 (no limit).
        output (str, optional): The knowledge base key under which the final
                                constructed prompt (as a list of message dictionaries)
                                will be stored. Defaults to "BUILD_GPT_PROMPT_OUTPUT".

    Example:
    ["custom", { "name": "build_gpt_prompt",
                 "args": {
                            "system_prompt": "You are a helpful assistant.",
                            "user_prompt": "Based on these documents: {docs}, answer the question: {query}",
                            "query": "What is the capital of France?",
                            "history": [],
                            "media_content": [],
                            "documents": "France is a country in Europe. Its capital is Paris.",
                            "max_tokens": 5000,
                            "output": "FINAL_LLM_PROMPT"
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the prompt building logic.

        This method retrieves and validates all input arguments, constructs
        the prompt by combining system, user, history, and document content,
        and then manages the prompt's token size by truncating history or
        documents if `max_tokens` is specified and exceeded. The final prompt
        is stored in the knowledge base.
        """
        system_prompt = self.parse_simple_input(
            key="system_prompt", check_for_type="str"
        )

        if system_prompt is None:
            system_prompt = ""

        user_prompt = self.parse_simple_input(key="user_prompt", check_for_type="str")

        if user_prompt is None:
            user_prompt = ""

        query = self.parse_simple_input(key="query", check_for_type="str")

        if query is None:
            query = ""

        documents = self.parse_simple_input(key="documents", check_for_type="str")

        if documents is None:
            documents = ""

        history = self.parse_simple_input(key="history", check_for_type="list")

        if history is None:
            history = []

        max_tokens = self.parse_simple_input(key="max_tokens", check_for_type="int")

        if max_tokens is None:
            max_tokens = -1

        system_content = []
        if system_prompt:
            system_content = [{"role": "system", "content": system_prompt}]

        user_content = []
        user_text_content = ""
        if user_prompt:
            user_query_prompt = user_prompt.replace("{query}", query)

            if documents:
                user_text_content = user_query_prompt.replace("{docs}", documents),
            elif "{docs}" in user_query_prompt:  # without doc
                user_text_content = query
            else:
                user_text_content = user_query_prompt

            user_content = [{
                "type": "text",
                "text": user_text_content
            }]

        media_content = self.parse_simple_input(key="media_content", check_for_type="list")

        if media_content:
            user_content.extend(media_content)

        user_content = [{"role": "user", "content": user_content}]

        outmesg = system_content + history + user_content

        if max_tokens > 0:
            mesg_token_size = calc_token_size(str(outmesg))
            while history and mesg_token_size > max_tokens:
                history = history[2:]  # gradually purge history
                outmesg = system_content + history + user_content
                mesg_token_size = calc_token_size(str(outmesg))

            if mesg_token_size > max_tokens:
                if documents:
                    doc_token_size = calc_token_size(documents)
                    doc_token_size -= mesg_token_size - max_tokens
                    logger.warning(
                        "build_gpt_prompt: total prompt token size %d exceeds max allowed token size %d, clipping the search doc.",
                        mesg_token_size,
                        max_tokens,
                    )
                    clipped_docs = cut_string(s=documents, n_tokens=doc_token_size - 10)
                    user_content = [
                        {
                            "role": "user",
                            "content": user_query_prompt.replace(
                                "{docs}", clipped_docs
                            ),
                        }
                    ]
                    outmesg = system_content + user_content
                else:  # it seems our user prompt is also too big
                    logger.error(
                        "build_gpt_prompt: total prompt token size %d exceeds max allowed token size %d, trim down system and user prompt.",
                        mesg_token_size,
                        max_tokens,
                    )
                    await self.failed()
                    return

        logger.debug("build_gpt_prompt: final prompt %s", outmesg)

        if "output" in self.details and isinstance(self.details["output"], str):
            self.kb[self.details["output"]] = outmesg
        else:
            self.kb["BUILD_GPT_PROMPT_OUTPUT"] = outmesg

        await self.succeeded()
