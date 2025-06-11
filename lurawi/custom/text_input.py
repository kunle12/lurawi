from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class text_input(CustomBehaviour):
    """!@brief process prompted user text inputs.
    Example:
    ["custom", { "name": "text_input",
                 "args": {
                            "prompt":"Enter your name",
                            "output":"GUESTNAME"
                          }
                }
    ]
    text input takes prompted user input and put the text in knowledgebase
    with a specified output.
    """

    def __init__(self, kb, details):
        super().__init__(kb, details)
        self.data_key = None

    async def run(self):
        prompt = ""

        self.data_key = self.parse_simple_input(key="output", check_for_type="str")

        if self.data_key is None:
            logger.error("text_input: missing or invalid output(str)")
            await self.failed()
            return

        if "prompt" in self.details:
            prompt = self.details["prompt"]
            if isinstance(prompt, list) and len(prompt) == 2:
                to_say, keys = prompt
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
                    print(f"Invalid prompt {prompt}). action should of form- {sample}")
                    prompt = ""
            elif not isinstance(prompt, str):
                print(f"Invalid prompt {prompt}).")
                prompt = ""

        self.register_for_user_message_updates()

        if prompt:
            await self.message(prompt)

    async def on_user_message_update(self, context):
        self.kb[self.data_key] = context.content
        await self.succeeded()
