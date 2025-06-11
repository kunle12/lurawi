import os
import simplejson as json
import time

from lurawi.custom_behaviour import CustomBehaviour
from openai import AsyncOpenAI
from lurawi.utils import is_indev, logger, DataStreamHandler, set_dev_stream_handler


class invoke_llm(CustomBehaviour):
    """!@brief invoke a Agent via OpenAI style
    Example:
    ["custom", { "name": "invoke_llm",
                 "args": {
                            "base_url": "https://localhost:8000",
                            "api_key": "token for the project",
                            "model": "gpt35",
                            "prompt": ["text prompt"],
                            "temperature": 0.9,
                            "max_tokens": 500,
                            "stream": False,
                            "response": "save text response from the llm",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note only limited parameters are supported in this call
    """

    async def run(self):
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

        model = self.details["model"]
        if isinstance(model, str) and model in self.kb:
            model = self.kb[model]

        prompt = self.details["prompt"]
        if isinstance(prompt, str) and prompt in self.kb:
            prompt = self.kb[prompt]

        if isinstance(prompt, list):
            if len(prompt) == 2 and isinstance(prompt[1], list):
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
                resolved_prompts = []
                for item in prompt:
                    if not isinstance(item, dict):
                        logger.error(
                            "invoke_llm: invalid payload: invalid composite prompt format"
                        )
                        await self.failed()
                        return
                    item_payload = json.loads(json.dumps(item))
                    for k, v in item_payload.items():
                        if (
                            isinstance(v, list)
                            and len(v) == 2
                            and isinstance(v[1], list)
                        ):
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
                            value = self.kb[v]
                            if isinstance(value, list) and len(value) > 1:
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
            logger.error(f"invoke_llm: failed to call Agent {model}: {err}")
            self.kb["ERROR_MESSAGE"] = str(err)
            await self.failed()
            self.kb["ERROR_MESSAGE"] = ""
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
