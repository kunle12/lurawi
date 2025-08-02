"""
This module defines the core agent classes for the Lurawi platform,
including a base agent, an AutoGen-compatible agent, and an AWS-compatible agent.
It handles asynchronous operations, agent initialization, behaviour loading,
and interaction with the activity manager.
"""

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

from lurawi.utils import logger
from lurawi.activity_manager import ActivityManager

STANDARD_GENAI_CONFIGS = [
    "PROJECT_NAME",
    "PROJECT_ACCESS_KEY",
]


class AsyncioLoopHandler:
    """
    Manages an asyncio event loop for synchronous execution of asynchronous code.

    This class provides a context manager to ensure a new event loop is created
    and set for the current thread if one is not already running or is closed.
    It also offers a method to run an asynchronous coroutine synchronously.
    """

    def __init__(self):
        """
        Initializes the AsyncioLoopHandler with no active event loop.
        """
        self._loop = None

    @contextlib.contextmanager
    def get_loop(self):
        """
        Provides an asyncio event loop as a context manager.

        If no loop is active or the current loop is closed, a new loop is created
        and set as the current event loop for the thread.

        Yields:
            asyncio.AbstractEventLoop: The active asyncio event loop.
        """
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
        """
        Runs an asynchronous coroutine synchronously within the managed event loop.

        Args:
            coro (Coroutine): The asynchronous coroutine to run.

        Returns:
            Any: The result of the executed coroutine.
        """
        with self.get_loop() as loop:
            return loop.run_until_complete(coro)


class LurawiAgent(object):
    """
    Base class for Lurawi agents, providing core functionalities for agent management,
    behaviour loading, knowledge base integration, and asynchronous execution.

    This agent manages its own lifecycle, including startup, loading of
    behaviours and knowledge, and interaction with the ActivityManager to
    orchestrate workflows.
    """

    def __init__(self, name: str, behaviour: str, workspace: str = ".") -> None:
        """
        Initializes a new instance of the LurawiAgent.

        Args:
            name (str): The name of the agent.
            behaviour (str): The name of the behaviour file (without .json extension)
                             to load for this agent.
            workspace (str, optional): The workspace directory for the agent.
                                       Defaults to current directory ".".
                                       Can be overridden by LURAWI_WORKSPACE environment variable.
        """
        self._name = name
        self.startup_time = time.time()
        self._workspace = os.environ.get("LURAWI_WORKSPACE", workspace)
        self._async_loop_handler = AsyncioLoopHandler()

        if not os.path.exists(self._workspace):
            logger.warning("lurawi_agent: misconfigured workspace path")
            self._workspace = "."

        self.knowledge = {"LURAWI_WORKSPACE": self._workspace}
        self.behaviours = self._load_behaviours(behaviour)
        self.agent_id = f"agent_{uuid.uuid4()}"

        self._activity_manager = ActivityManager(
            self.agent_id, name, self.behaviours, self.knowledge
        )

    def _load_knowledge(self, kbase: str) -> bool:
        """
        Loads knowledge from a specified JSON file into the agent's knowledge base.

        Args:
            kbase (str): The base name of the knowledge file (e.g., "my_knowledge").
                         The file is expected to be located at `{workspace}/{kbase}.json`.

        Returns:
            bool: True if the knowledge was loaded successfully or if no file was provided,
                  False if an error occurred during loading.
        """
        kbase_path = f"{self._workspace}/{kbase}.json"

        try:
            if os.path.exists(kbase_path):
                with open(kbase_path, encoding="utf-8") as data:
                    json_data = json.load(data)
            else:
                logger.warning(
                    "load_knowledge: no knowledge file %s is provided.", kbase
                )
                return True
        except Exception as err:
            logger.error(
                "load_knowledge: unable to load knowledge file '%s':%s", kbase_path, err
            )
            return False

        self.knowledge.update(json_data)

        logger.info("load_knowledge: Knowledge file %s is loaded!", kbase_path)

        # check for custom domain specific language analysis model
        return True

    def _load_behaviours(self, behaviour: str):
        """
        Loads agent behaviours from a specified JSON file and integrates associated knowledge.

        This method attempts to load a behaviour definition file and its corresponding
        knowledge file. It also incorporates standard environment variables into the
        agent's knowledge base.

        Args:
            behaviour (str): The base name of the behaviour file (e.g., "my_behaviour").
                             The file is expected to be located at `{workspace}/{behaviour}.json`.

        Returns:
            dict: A dictionary containing the loaded behaviours. Returns an empty dictionary
                  if the behaviour file is not found, is misconfigured, or an error occurs.
        """
        loaded_behaviours = {}

        if behaviour.endswith(".json"):
            logger.warning("load_behaviours: extension .json is not required")
            return loaded_behaviours

        behaviour_file = f"{self._workspace}/{behaviour}.json"

        try:
            if os.path.exists(behaviour_file):
                with open(behaviour_file, encoding="utf-8") as data:
                    loaded_behaviours = json.load(data)
            else:
                logger.error(
                    "load_behaviours: no custom behaviour file %s is provided.",
                    behaviour_file,
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
        """
        Synchronously runs the agent's workflow with a given message.

        This method uses the internal AsyncioLoopHandler to execute the
        asynchronous `arun_agent` method.

        Args:
            message (str): The input message for the agent.
            **kwargs: Additional keyword arguments to pass to the workflow.

        Returns:
            str: The response from the agent's workflow.
        """
        return self._async_loop_handler.run_async(
            self.arun_agent(message=message, **kwargs)
        )

    async def arun_agent(self, message: str, **kwargs) -> str:
        """
        Asynchronously runs the agent's workflow with a given message.

        If the activity manager is already initialized, it continues the existing workflow.
        Otherwise, it initializes the activity manager and starts a new user workflow.

        Args:
            message (str): The input message for the agent.
            **kwargs: Additional keyword arguments to pass to the workflow.

        Returns:
            str: The response from the agent's workflow, or a system busy message
                 if no response is received.
        """
        input_data = kwargs
        input_data["message"] = message
        if self._activity_manager.is_initialised:
            response = await self._activity_manager.continue_workflow(data=input_data)
        else:
            await self._activity_manager.init()
            response = await self._activity_manager.start_user_workflow(data=input_data)
        if response:
            return json.loads(self._activity_manager.get_response().body)["response"]
        return "System is busy, please try later."

class LurawiAutoGenAgent(BaseChatAgent, LurawiAgent):
    """
    A Lurawi agent designed to be compatible with the AutoGen framework.

    This class extends both `BaseChatAgent` from AutoGen and `LurawiAgent`,
    integrating Lurawi's workflow capabilities into the AutoGen ecosystem.
    """

    def __init__(
        self,
        name: str,
        behaviour: str,
        description: str = "A lurawi agent for AutoGen",
        workspace: str = ".",
    ):
        """
        Initializes a new instance of the LurawiAutoGenAgent.

        Args:
            name (str): The name of the agent.
            behaviour (str): The name of the behaviour file (without .json extension)
                             to load for this agent.
            description (str, optional): A description of the agent for AutoGen.
                                         Defaults to "A lurawi agent for AutoGen".
            workspace (str, optional): The workspace directory for the agent.
                                       Defaults to current directory ".".
        """
        BaseChatAgent.__init__(self, name=name, description=description)
        LurawiAgent.__init__(self, name=name, behaviour=behaviour, workspace=workspace)

    @property
    def produced_message_types(self) -> Sequence[type[ChatMessage]]:
        """
        The types of final response messages that the assistant agent produces.

        Returns:
            Sequence[type[ChatMessage]]: A tuple containing `TextMessage` as the
                                         produced message type.
        """
        message_types: List[type[ChatMessage]] = [TextMessage]
        return tuple(message_types)

    async def on_messages(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        """
        Handles incoming chat messages from AutoGen and processes them using the Lurawi agent.

        Args:
            messages (Sequence[ChatMessage]): A sequence of chat messages received.
            cancellation_token (CancellationToken): A token to signal cancellation.

        Returns:
            Response: An AutoGen `Response` object containing the aggregated
                      response from the Lurawi agent.
        """
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
        """
        Raises an AssertionError as LurawiAutoGenAgent does not support streaming.

        Args:
            messages (Sequence[ChatMessage]): A sequence of chat messages.
            cancellation_token (CancellationToken): A token to signal cancellation.

        Raises:
            AssertionError: Always, as streaming is not supported.
        """
        raise AssertionError("LurawiAutoGenAgent does not support streaming.")

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """
        Resets the assistant agent to its initialization state.

        Currently, this method does not perform any state clearing.
        TODO: Implement clearing of Lurawi agent state.

        Args:
            cancellation_token (CancellationToken): A token to signal cancellation.
        """
        pass  # TODO clear lurawi state


@dataclass(kw_only=True)
class LurawiAWSAgentOptions(AWSAgentOption):
    """
    Data class for options specific to the Lurawi AWS Agent.

    Extends `AWSAgentOption` to include Lurawi-specific configuration
    such as `behaviour` and `workspace`.
    """

    behaviour: str
    workspace: str = "."


class LurawiAWSAgent(AWSAgent, LurawiAgent):
    """
    A Lurawi agent designed to be compatible with the AWS multi-agent orchestrator.

    This class extends both `AWSAgent` and `LurawiAgent`, enabling Lurawi's
    workflow capabilities within an AWS-orchestrated multi-agent environment.
    """

    def __init__(self, options: LurawiAWSAgentOptions):
        """
        Initializes a new instance of the LurawiAWSAgent.

        Args:
            options (LurawiAWSAgentOptions): Configuration options for the agent,
                                             including name, behaviour, and workspace.
        """
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
        """
        Processes an incoming request from the AWS multi-agent orchestrator.

        This method takes the input text and other conversation details,
        runs the Lurawi agent's workflow, and returns the response in a
        `ConversationMessage` format suitable for the AWS orchestrator.

        Args:
            input_text (str): The input text from the user.
            user_id (str): The ID of the user.
            session_id (str): The ID of the current session.
            chat_history (List[ConversationMessage]): The history of the conversation.

        Returns:
            ConversationMessage: A message containing the agent's response,
                                 formatted for the AWS orchestrator.
        """
        response = await self.run_agent(input_text)

        return ConversationMessage(
            role=ParticipantRole.ASSISTANT.value, content=[{"text": response}]
        )
