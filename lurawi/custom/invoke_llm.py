"""
Custom behaviour for invoking Large Language Models (LLMs) via an OpenAI-compatible API.

This module defines the `invoke_llm` class, which allows the system to send
prompts to an LLM, manage streaming responses, and store the LLM's output
in the knowledge base.
"""

import os
import time
import simplejson as json

from openai import AsyncOpenAI
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import is_indev, logger, DataStreamHandler, set_dev_stream_handler


class invoke_llm(CustomBehaviour):
    """!@brief Invokes a Large Language Model (LLM) using an OpenAI-compatible API.

    This custom behaviour facilitates interaction with LLMs by constructing
    and sending prompts, handling both synchronous and streaming responses,
    and storing the LLM's generated content in the knowledge base.

    Args:
        base_url (str): The base URL of the OpenAI-compatible API endpoint.
                        Can be a direct string or a knowledge base key.
        api_key (str): The API key for authentication with the LLM service.
                       Can be a direct string or a knowledge base key.
        model (str): The name of the LLM model to use (e.g., "gpt-3.5-turbo").
                     Can be a direct string or a knowledge base key.
        prompt (str or list): The input prompt for the LLM.
                              - If a string, it's the direct prompt text.
                              - If a list, it can be:
                                - `["template {}", ["key1", "key2"]]`: A template string
                                  with placeholders `{}` and a list of knowledge base
                                  keys whose values will replace the placeholders.
                                - `[{"role": "user", "content": "..."}]`: A list of
                                  message dictionaries in OpenAI chat format.
                                  Placeholders within content can also be resolved.
        temperature (float, optional): Controls the randomness of the output.
                                       Higher values mean more random. Defaults to 0.6.
        max_tokens (int, optional): The maximum number of tokens to generate in
                                    the LLM's response. Defaults to 512.
        stream (bool, optional): If `True`, the LLM response will be streamed.
                                 If `False`, the full response is awaited.
                                 Defaults to `False`.
        response (str, optional): The knowledge base key under which the LLM's
                                  text response will be stored. If the key
                                  already exists and its value is a list, the
                                  response will be appended. Defaults to "LLM_RESPONSE".
        success_action (list, optional): An action to execute if the LLM invocation
                                         is successful (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if the LLM invocation
                                        fails (e.g., `["play_behaviour", "next"]`).

    Example:
    ["custom", { "name": "invoke_llm",
                 "args": {
                            "base_url": "https://api.openai.com/v1",
                            "api_key": "OPENAI_API_KEY",
                            "model": "gpt-3.5-turbo",
                            "prompt": [{"role": "user", "content": "Tell me a story about {}."}],
                            "temperature": 0.7,
                            "max_tokens": 200,
                            "stream": False,
                            "response": "MY_LLM_STORY",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the LLM invocation logic.

        This method retrieves and validates all LLM configuration parameters
        (base URL, API key, model, prompt, temperature, max tokens, stream).
        It constructs the prompt, makes the asynchronous call to the LLM,
        and handles the response, either streaming it or storing the full
        content in the knowledge base. Error handling for API calls is included.
        """
        invoke_time = time.time()

        base_url = self.parse_simple_input(key="base_url", check_for_type="str")

        if base_url is None:
            logger.error("invoke_llm: missing or invalid base_url(str)")
            await self.failed()
            return

        api_key = self.parse_simple_input(key="api_key", check_for_type="str")

        if api_key is None:
            logger.error("invoke_llm: missing or invalid api_key(str)")
            await self.failed()
            return

        model = self.parse_simple_input(key="model", check_for_type="str")

        if model is None:
            logger.error("invoke_llm: missing or invalid model(str)")
            await self.failed()
            return

        if "prompt" not in self.details:
            logger.error("invoke_llm: missing input text prompt")
            await self.failed()
            return

        prompt = self.details["prompt"]
        # Resolve prompt from KB if it's a key
        if isinstance(prompt, str) and prompt in self.kb:
            prompt = self.kb[prompt]

        # Handle different prompt formats
        if isinstance(prompt, list):
            if len(prompt) == 2 and isinstance(prompt[1], list):
                # Format: ["template {}", ["key1", "key2"]]
                keys = prompt[1]
                content = prompt[0]
                for key in keys:
                    if key in self.kb:
                        content = content.replace("{}", str(self.kb[key]), 1)
                    else:
                        _key = str(key).replace("_", " ")
                        content = content.replace("{}", _key, 1)
                prompt = content
            else:
                # Format: [{"role": "user", "content": "..."}] with potential nested placeholders
                resolved_prompts = []
                for item in prompt:
                    if not isinstance(item, dict):
                        logger.error(
                            "invoke_llm: invalid payload: invalid composite prompt format"
                        )
                        await self.failed()
                        return
                    item_payload = json.loads(json.dumps(item))  # Deep copy
                    for k, v in item_payload.items():
                        if (
                            isinstance(v, list)
                            and len(v) == 2
                            and isinstance(v[1], list)
                        ):
                            # Nested template: ["content {}", ["key"]]
                            content, keys = v
                            for key in keys:
                                if key in self.kb:
                                    content = content.replace(
                                        "{}", str(self.kb[key]), 1
                                    )
                                else:
                                    _key = str(key).replace("_", " ")
                                    content = content.replace("{}", _key, 1)
                            item_payload[k] = content
                        elif isinstance(v, str) and v in self.kb:
                            # Value is a KB key
                            value = self.kb[v]
                            if isinstance(value, list) and len(value) > 1:
                                # KB value is a template: ["content {}", ["key"]]
                                keys = value[1]
                                if not isinstance(keys, list):
                                    logger.error(
                                        "invoke_llm: invalid item_payload: invalid composite value format"
                                    )
                                    await self.failed()
                                    return
                                content = value[0]
                                for key in keys:
                                    if key in self.kb:
                                        content = content.replace(
                                            "{}", str(self.kb[key]), 1
                                        )
                                    else:
                                        _key = str(key).replace("_", " ")
                                        content = content.replace("{}", _key, 1)
                                item_payload[k] = content
                            else:
                                item_payload[k] = value
                    resolved_prompts.append(item_payload)
                prompt = resolved_prompts

        if isinstance(prompt, str):
            prompt = [{"role": "user", "content": prompt}]

        temperature = self.parse_simple_input(key="temperature", check_for_type="float")

        if temperature is None:
            logger.warning(
                "invoke_llm: missing or invalid temperature(float), using default to 0.6"
            )
            temperature = 0.6

        stream = self.parse_simple_input(key="stream", check_for_type="bool")

        if stream is None:
            stream = False

        max_tokens = self.parse_simple_input(key="max_tokens", check_for_type="int")

        if max_tokens is None:
            max_tokens = 512

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        response = None
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
            )
        except Exception as err:
            logger.error("invoke_llm: failed to call Agent %s: %s", model, err)
            self.kb["ERROR_MESSAGE"] = str(err)
            await self.failed()
            self.kb["ERROR_MESSAGE"] = ""  # Clear error message after handling
            return

        if stream:
            data_stream = DataStreamHandler(response=response)
            if is_indev():
                set_dev_stream_handler(data_stream)
                resp = {
                    "stream_endpoint": f"http://localhost:{os.getenv('PORT', 8081)}/dev/stream"
                }
                await self.message(status=200, data=resp)
            else:
                await self.message(status=200, data=data_stream)
        else:
            if "response" in self.details and isinstance(self.details["response"], str):
                result_variable = self.details["response"]
                if result_variable in self.kb and isinstance(
                    self.kb[result_variable], list
                ):
                    self.kb[result_variable].append(response.choices[0].message.content)
                else:
                    self.kb[result_variable] = response.choices[0].message.content
            else:
                self.kb["LLM_RESPONSE"] = response.choices[0].message.content
            await self.succeeded()
