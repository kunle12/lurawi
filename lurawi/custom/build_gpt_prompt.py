from lurawi.utils import cut_string, calc_token_size, logger
from lurawi.custom_behaviour import CustomBehaviour


class build_gpt_prompt(CustomBehaviour):
    """!@brief build custom GPT prompt
    Example:
    ["custom", { "name": "build_gpt_prompt",
                 "args": {
                            "system_prompt": "system prompt text",
                            "user_prompt": "user prompt text",
                            "query": "token for the user_prompt",
                            "history": [],
                            "documents": "search text",
                            "max_tokens": 5000,
                            "output": "final text output"
                          }
                }
    ]
    @note only limited parameters are supported in this call
    """

    async def run(self):
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
        if user_prompt:
            user_query_prompt = user_prompt.replace("{query}", query)

            if documents:
                user_content = [
                    {
                        "role": "user",
                        "content": user_query_prompt.replace("{docs}", documents),
                    }
                ]
            elif "{docs}" in user_query_prompt:  # without doc
                user_content = [{"role": "user", "content": query}]
            else:
                user_content = [{"role": "user", "content": user_query_prompt}]

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
                        mesg_token_size, max_tokens
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
                        mesg_token_size, max_tokens
                    )
                    await self.failed()
                    return

        logger.debug("build_gpt_prompt: final prompt %s", outmesg)

        if "output" in self.details and isinstance(self.details["output"], str):
            self.kb[self.details["output"]] = outmesg
        else:
            self.kb["BUILD_GPT_PROMPT_OUTPUT"] = outmesg

        await self.succeeded()
