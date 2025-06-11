import asyncio
import contextlib
import os
import simplejson as json
import time
import uuid

from autogen_core import CancellationToken
from autogen_agentchat.messages import AgentEvent, TextMessage, ChatMessage
from autogen_agentchat.agents._base_chat_agent import BaseChatAgent
from autogen_agentchat.base._chat_agent import Response
from dataclasses import dataclass
from multi_agent_orchestrator.agents import (
    Agent as AWSAgent,
    AgentOptions as AWSAgentOption,
)
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from typing import AsyncGenerator, List, Dict, Sequence, Any

from .utils import logger
from .activity_manager import ActivityManager

STANDARD_GENAI_CONFIGS = [
    "PROJECT_NAME",
    "PROJECT_ACCESS_KEY",
]


class AsyncioLoopHandler:
    def __init__(self):
        self._loop = None

    @contextlib.contextmanager
    def get_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        try:
            yield self._loop
        finally:
            # Optional: close the loop if needed
            # if not self._loop.is_closed():
            #     self._loop.close()
            pass

    def run_async(self, coro):
        with self.get_loop() as loop:
            return loop.run_until_complete(coro)


class LurawiAgent(object):
    """ """

    def __init__(self, name: str, behaviour: str, workspace: str = ".") -> None:
        self._name = name
        self.startup_time = time.time()
        self._workspace = os.environ.get("LURAWI_WORKSPACE", workspace)
        self._async_loop_handler = AsyncioLoopHandler()

        if not os.path.exists(self._workspace):
            logger.warning("lurawi_agent: misconfigured workspace path")
            self._workspace = "."

        self.knowledge = {"LURAWI_WORKSPACE": self._workspace}
        self.behaviours = self._load_behaviours(behaviour)
        self.agent_id = str(uuid.uuid4())

        self._activity_manager = ActivityManager(
            self.agent_id, name, self.behaviours, self.knowledge
        )

    def _load_knowledge(self, kbase: str) -> bool:
        kbase_path = f"{self._workspace}/{kbase}.json"

        try:
            if os.path.exists(kbase_path):
                with open(kbase_path) as data:
                    json_data = json.load(data)
            else:
                logger.warning(
                    "load_knowledge: no knowledge file %s is provided.", kbase
                )
                return True
        except Exception as err:
            logger.error(
                "load_knowledge: unable to load knowledge file '%s':%s",
                kbase_path, err
            )
            return False

        self.knowledge.update(json_data)

        logger.info("load_knowledge: Knowledge file %s is loaded!", kbase_path)

        # check for custom domain specific language analysis model
        return True

    def _load_behaviours(self, behaviour: str):
        loaded_behaviours = {}

        if behaviour.endswith(".json"):
            logger.warning("load_behaviours: extension .json is not required")
            return loaded_behaviours

        behaviour_file = f"{self._workspace}/{behaviour}.json"

        try:
            if os.path.exists(behaviour_file):
                with open(behaviour_file) as data:
                    loaded_behaviours = json.load(data)
            else:
                logger.error(
                    "load_behaviours: no custom behaviour file %s is provided.",
                    behaviour_file
                )
                return loaded_behaviours
        except Exception as err:
            logger.error("Cannot load behaviours %s: %s", behaviour_file, err)
            return loaded_behaviours

        if "default" not in loaded_behaviours:
            logger.error("missing default in custom behaviour file %s", behaviour_file)
            return loaded_behaviours

        if not self._load_knowledge(behaviour + "_knowledge"):
            logger.info("No custom knowledge for new behaviours is loaded")

        # load any standard environmental variables overwrite
        # the existing knowledge.
        for config in STANDARD_GENAI_CONFIGS:
            if config in os.environ:
                self.knowledge[config] = os.environ[config]

        logger.info("load_behaviours: behaviours file %s is loaded!", behaviour_file)
        return loaded_behaviours

    def run_agent(self, message: str, **kwargs) -> str:
        return self._async_loop_handler.run_async(
            self.arun_agent(message=message, **kwargs)
        )

    async def arun_agent(self, message: str, **kwargs) -> str:
        input_data = kwargs
        input_data["message"] = message
        if self._activity_manager.is_initialised:
            response = await self._activity_manager.continue_workflow(data=input_data)
        else:
            await self._activity_manager.init()
            response = await self._activity_manager.start_user_workflow(data=input_data)
        if response:
            return json.loads(self._activity_manager.get_response().body)["response"]
        else:
            return "System is busy, please try later."


class LurawiAutoGenAgent(BaseChatAgent, LurawiAgent):
    def __init__(
        self,
        name: str,
        behaviour: str,
        description: str = "A lurawi agent for AutoGen",
        workspace: str = ".",
    ):
        BaseChatAgent.__init__(self, name=name, description=description)
        LurawiAgent.__init__(self, name=name, behaviour=behaviour, workspace=workspace)

    @property
    def produced_message_types(self) -> Sequence[type[ChatMessage]]:
        """The types of final response messages that the assistant agent produces."""
        message_types: List[type[ChatMessage]] = [TextMessage]
        return tuple(message_types)

    async def on_messages(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        resp = []
        for chat_message in messages:
            resp.append(await self.run_agent(chat_message.content))

        resp_text = "\n".join(resp)
        return Response(
            chat_message=TextMessage(content=resp_text, source=self.name),
            inner_messages=[],
        )

    async def on_messages_stream(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[AgentEvent | ChatMessage | Response, None]:
        raise AssertionError("LurawiAutoGenAgent does not support streaming.")

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """Reset the assistant agent to its initialization state."""
        pass  # TODO clear lurawi state


@dataclass(kw_only=True)
class LurawiAWSAgentOptions(AWSAgentOption):
    behaviour: str
    workspace: str = "."


class LurawiAWSAgent(AWSAgent, LurawiAgent):
    def __init__(self, options: LurawiAWSAgentOptions):
        AWSAgent.__init__(self, options=options)
        LurawiAgent.__init__(
            self,
            name=options.name,
            behaviour=options.behaviour,
            workspace=options.workspace,
        )

    async def process_request(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        chat_history: List[ConversationMessage],
    ) -> ConversationMessage:
        response = await self.run_agent(input_text)

        return ConversationMessage(
            role=ParticipantRole.ASSISTANT.value, content=[{"text": response}]
        )
