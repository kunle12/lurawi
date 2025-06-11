import simplejson as json

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class populate_prompt(CustomBehaviour):
    """!@brief fill up a prompt text with key values.
    Example:
    ["custom", { "name": "populate_prompt",
                 "args": {
                            "prompt_text": "prompt text",
                            "replace": { "{query}": "somevalue" },
                            "output": "output string"
                          }
                }
    ]
    """

    async def run(self):
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

        replace = json.loads(json.dumps(self.details["replace"]))
        for k, v in replace.items():
            if v in self.kb:
                value = self.kb[v]
                if isinstance(value, list) and len(value) > 1:
                    keys = value[1]
                    if not isinstance(keys, list):
                        logger.error(
                            "populate_prompt: invalid replace: invalid composite value format"
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
                    replace[k] = content
                else:
                    replace[k] = value

        logger.debug(f"final replacement string {replace}")

        for k, v in replace.items():
            prompt_text = prompt_text.replace(k, v)

        if "output" in self.details and isinstance(self.details["output"], str):
            self.kb[self.details["output"]] = prompt_text
        else:
            self.kb["PROMPT_TEXT"] = prompt_text
        await self.succeeded()
