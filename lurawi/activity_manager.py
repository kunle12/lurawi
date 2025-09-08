# pylint: disable=dangerous-default-value, too-many-lines

import asyncio
import importlib
import random
import re
import time
import uuid
from typing import Dict, Any
from threading import Lock as mutex
import simplejson as json

from fastapi.responses import JSONResponse, StreamingResponse

from .calculate import calculate
from .callbackmsg_manager import RemoteCallbackMessageUpdateManager
from .compare import compare
from .custom_behaviour import CustomBehaviour, DataStreamHandler
from .usermsg_manager import UserMessageUpdateManager
from .utils import write_http_response, logger


class ActivityManager:
    """
    Manages activities, behaviours, and actions for the Lurawi system.

    This class is responsible for loading behaviours, executing actions, managing user interactions,
    and maintaining the knowledge state. It handles the flow of activities, including queuing,
    suspending, and resuming actions.
    """

    def __init__(
        self, uid: str, name: str, behaviour, knowledge: Dict, system_service: Dict = {}
    ):
        """
        Initialize the ActivityManager with user information and behaviours.

        Args:
            uid: User identifier
            name: User name
            behaviour: Dictionary containing behaviour definitions
            knowledge: Dictionary containing knowledge base information
        """
        self.knowledge = json.loads(json.dumps(knowledge))
        self.knowledge["USER_ID"] = uid
        self.knowledge["USER_NAME"] = name
        self.knowledge["USER_DATA"] = {}
        self.knowledge["CURRENT_TURN_CONTEXT"] = ""
        self.knowledge["CURRENT_SESSION_ID"] = ""
        self.knowledge["MODULES"] = {}
        self.knowledge["LURAWI_SYSTEM_SERVICES"] = system_service
        self.knowledge["__MUTEX__"] = mutex()
        self.access_time = -1
        self._agent_mode = uid.startswith("agent_")

        self.behaviours = {}
        self.resources = {}
        self.active_behaviour = None
        self.custom_behaviours = {}
        self.activity_index = -1
        self.chained_actions = {}
        self.running_actions = {}
        self.pending_actions = []
        self.suspended_actions = {}  # suspended actions are all expected to be custom
        self.action_complete_cb = None
        self.action_complete_cb_args = None
        self.activity_complete_cb = None
        # notify external (not related to behaviour/actions) module of the completion of
        # action it is interested in.
        self.external_notification_cb = None
        self.actions_lined_up = False
        self.current_action_id = ""
        self.on_remote_play_next_activity = False
        self.continue_playing = False
        self.engagement_action = None
        self.disengagement_action = None
        self.in_user_interaction = False
        self.simple_json_data_check = re.compile(r"^{.+}$")
        self.userdata_action = None

        self.knowledge["MODULES"]["ActivityManager"] = self

        self.load_behaviours(behaviour)

        self.usermessage_manager = UserMessageUpdateManager(self.knowledge)
        self.callbackmessage_manager = RemoteCallbackMessageUpdateManager(
            self.knowledge
        )

        self.knowledge["MESG_FUNC"] = self.send_message

        self.pending_behaviours = {}
        self.pending_knowledge = {}
        self.on_pending_complete = None
        self.response = None
        self._discord_message = None
        self._is_initialised = False

    @property
    def is_initialised(self):
        """
        Check if the ActivityManager has been initialized.

        Returns:
            bool: True if initialized, False otherwise
        """
        return self._is_initialised

    async def init(self):
        """
        Initialize the ActivityManager asynchronously.

        If already initialized, this method returns immediately.
        Otherwise, it marks the manager as initialized and starts the first activity.
        """
        if self._is_initialised:
            return

        await self.play_next_activity()
        self._is_initialised = True

    async def start_user_workflow(self, session_id: str = "", context: Any = None, data: Dict = {}):
        """
        Initiates a user workflow, setting up the session and context for interaction.

        This method prepares the system for a new user interaction by setting the current
        turn context and session ID. It then attempts to load any pending behaviours.
        If an engagement action is defined, it will be played; otherwise, the workflow
        will proceed directly to `continue_workflow`.

        Args:
            session_id (str, optional): A unique identifier for the current session.
                                        Defaults to an empty string, in which case a new UUID is generated.
            context (Any, optional): The context for the current turn. If None, a new UUID is generated.
            data (Dict, optional): A dictionary containing user-provided data relevant to the workflow.
                                   Defaults to an empty dictionary.

        Returns:
            bool: True if the workflow was successfully initiated or continued, False if
                  the system is already in a user interaction.
        """
        if self.in_user_interaction:
            return False

        await self.load_pending_behaviour_if_exists()

        self.knowledge["CURRENT_TURN_CONTEXT"] = context if context else str(uuid.uuid4())
        self.knowledge["CURRENT_SESSION_ID"] = session_id

        logger.debug(
            "workflow: receiving user %s input %s activity_id %s",
            self.knowledge["USER_ID"],
            data,
            self.knowledge["CURRENT_TURN_CONTEXT"],
        )
        if self.engagement_action:
            self.knowledge["ACCESS_TIME"] = self.access_time = time.time()
            self.knowledge["USER_DATA"] = data
            return await self.play_action(
                "workflow_engagement",
                [self.engagement_action],
                external_notification_cb=self.engage_complete,
            )

        return await self.continue_workflow(data=data)

    async def stop_user_workflow(self):
        """
        Stop the current user workflow.

        Clears the current turn context and plays the disengagement action if defined.
        """
        self.knowledge["CURRENT_TURN_CONTEXT"] = None
        if self.disengagement_action is None:
            return
        await self.play_disruptive_action(
            "workflow_disengagement",
            [self.disengagement_action],
            external_notification_cb=self.disengage_complete,
        )

    async def load_pending_behaviour_if_exists(self):
        """
        Load pending behaviours if they exist.

        Updates knowledge with pending knowledge, loads pending behaviours,
        plays the next activity, and calls the completion callback.

        Note: self.on_pending_complete is expected to be a callable that may or may not be awaitable.
        The method will attempt to await it, so it should be compatible with the await syntax.

        Returns:
            bool: True if pending behaviours were loaded, False otherwise
        """
        if not self.pending_behaviours or not self.on_pending_complete:
            return False

        if self.pending_knowledge:
            self.knowledge.update(json.loads(json.dumps(self.pending_knowledge)))
            self.pending_knowledge = {}

        self.load_behaviours(self.pending_behaviours)
        self.pending_behaviours = {}

        logger.info("pending behaviour loaded")
        await self.play_next_activity()  # run initial activity

        await self.on_pending_complete()
        self.on_pending_complete = None
        return True

    async def engage_complete(self):
        """
        Callback for when engagement is complete.

        Sets the in_user_interaction flag to True.
        """
        logger.debug("interaction engagement completed")
        self.in_user_interaction = True

    async def disengage_complete(self):
        """
        Callback for when disengagement is complete.

        Sets the in_user_interaction flag to False.
        """
        logger.debug("interaction disengagement completed")
        self.in_user_interaction = False

    async def user_data_complete(self):
        """
        Callback for when user data processing is complete.

        Sets the in_user_interaction flag to False.
        """
        logger.debug("interaction user data completed")
        self.in_user_interaction = False

    async def continue_workflow(self, context: Any = None, activity_id: str = "", data: Dict = {}):
        """
        Continues an existing user workflow, processing new input and updating the system state.

        This method is responsible for advancing the workflow based on new user data or
        a specified activity ID. It updates the access time, processes user messages
        through the `usermessage_manager`, and triggers an update to the user data
        if necessary.

        Args:
            context (Any, optional): The context for the current turn. If provided, it
                                     overrides the existing `CURRENT_TURN_CONTEXT`.
            activity_id (str, optional): An identifier for the specific activity to continue.
                                         If different from the current turn context, it updates it.
            data (Dict, optional): A dictionary containing new user data to be processed.
                                   Defaults to an empty dictionary.

        Returns:
            bool: True if the workflow was successfully continued.
        """
        self.knowledge["ACCESS_TIME"] = self.access_time = time.time()
        self.knowledge["USER_DATA"] = data

        if context:
            self.knowledge["CURRENT_TURN_CONTEXT"] = context
            if await self.usermessage_manager.process_user_messages(data):
                await self.on_update_user_data(data=data)
        elif (
            activity_id and activity_id != self.knowledge["CURRENT_TURN_CONTEXT"]
        ) or await self.usermessage_manager.process_user_messages(data):
            self.knowledge["CURRENT_TURN_CONTEXT"] = activity_id
            await self.on_update_user_data(data=data)
        return True

    def get_current_session_id(self):
        """
        Get the current session ID.

        Returns:
            str: The current turn context, which serves as the session ID
        """
        return self.knowledge["CURRENT_TURN_CONTEXT"]

    def set_pending_behaviours(self, behaviours, knowledge, on_complete):
        """
        Set pending behaviours to be loaded later.

        Args:
            behaviours: Dictionary containing behaviour definitions
            knowledge: Dictionary containing knowledge to be merged
            on_complete: Callback function to be called when behaviours are loaded
        """
        if not behaviours or not callable(on_complete):
            logger.error("invalid pending behaviour call")

        self.pending_behaviours = behaviours
        self.pending_knowledge = json.loads(json.dumps(knowledge))
        self.on_pending_complete = on_complete

    def load_behaviours(self, behaviour, force=False):
        """
        Load behaviours from the provided behaviour definition.

        Finds the default behaviour and sets it as the active behaviour.

        Args:
            behaviour: Dictionary containing behaviour definitions
            force: If True, clear running actions before loading behaviours

        Returns:
            bool: True if behaviours were loaded successfully, False otherwise
        """
        if not behaviour:
            logger.error("No new behaviour available")
            return False

        if self.is_busy():
            if force:
                self.clear_running_actions()
                logger.warning(
                    "System is busy, clear running actions and force load behaviours."
                )
            else:
                logger.error("System is busy, cannot load behaviours.")
                return False

        active_behaviour = None
        try:
            default_action = behaviour["default"]
            for be in behaviour["behaviours"]:
                if be["name"] == default_action:
                    active_behaviour = be["actions"]
                    break
        except Exception as _:
            logger.error("Corrupted behaviours file")
            return False

        if active_behaviour is None:
            logger.error("No matching default behaviour found.")
            return False

        self.behaviours = behaviour
        self.activity_index = -1
        self.active_behaviour = active_behaviour

        self.clear_running_actions()

        return True

    def select_activity(
        self, active_section
    ):  # pylint: disable=too-many-return-statements
        """
        Select an activity based on the active section.

        Handles different formats for specifying activities:
        - "next": Continue with the next activity
        - "previous": Go back to the previous activity
        - Knowledge key: Use the value from knowledge as the activity
        - Numeric: Select activity by index
        - "behaviour:index": Select activity from a specific behaviour

        Args:
            active_section: Specification for which activity to select

        Returns:
            bool: True if activity was selected successfully, False otherwise
        """
        if not active_section:
            logger.error("select activity no active section")
            return True
        if active_section == "next":
            # return self.set_activity_index(self.activity_index)
            return True
        elif active_section == "previous":
            return self.set_activity_index(self.activity_index - 2)
        elif active_section in self.knowledge:
            return self.select_activity(self.knowledge[active_section])
            # return self.set_activity_index(self.knowledge[active_section])
        elif active_section.strip().isdigit():
            return self.set_activity_index(int(active_section) - 1)
        elif ":" in active_section:  # "queensland_demo:2"
            if len(active_section.split(":")) == 2:
                (behave, index) = active_section.split(":")
                if (
                    self.set_active_behaviour(behave.strip())
                    and index.strip().isdigit()
                ):
                    return self.set_activity_index(int(index) - 1)
            else:
                logger.error(
                    "Expected activity to be 'some_behaviour:1', got %s", active_section
                )
                return False
        else:
            return self.set_active_behaviour(active_section.strip())

    def set_active_behaviour(self, name):
        """
        Set the active behaviour by name.

        Finds the behaviour with the given name and sets it as active.

        Args:
            name: Name of the behaviour to set as active

        Returns:
            bool: True if behaviour was set successfully, False otherwise
        """
        # if self.is_busy():
        #     return False

        for beh in self.behaviours["behaviours"]:
            if name == beh["name"]:
                self.active_behaviour = beh["actions"]
                self.activity_index = -1
                if "USER_INPUTS_CACHE" in self.knowledge:
                    self.knowledge["__MUTEX__"].acquire()
                    self.knowledge["USER_INPUTS_CACHE"] = []  # reset cache
                    self.knowledge["__MUTEX__"].release()
                logger.debug("Active behaviour set to %s", name)
                return True
        logger.error("Cannot find %s behaviour", name)
        return False

    def set_activity_index(self, new_index):
        """
        Set the current activity index.

        Args:
            new_index: New index for the current activity

        Returns:
            bool: True if index was set successfully, False otherwise
        """
        if not self.active_behaviour:
            logger.error("No active behaviour. please check.")
            return False
        # if new_index < 0 or new_index >= len(self.active_behaviour):
        if new_index < -1 or new_index >= len(self.active_behaviour):
            logger.error("Cannot set Activity index - %d, out of bounds.", new_index)
            return False

        self.activity_index = new_index
        return True

    def set_engagement_action(self, action):
        """
        Set the engagement action.

        Args:
            action: Action to be executed during engagement
        """
        self.engagement_action = action

    def set_disengagement_action(self, action):
        """
        Set the disengagement action.

        Args:
            action: Action to be executed during disengagement
        """
        self.disengagement_action = action

    def set_user_data_action(self, action):
        """
        Set the user data action.

        Args:
            action: Action to be executed when processing user data
        """
        self.userdata_action = action

    def update_knowledge(self, info):
        """
        Update the knowledge base with new information.

        Args:
            info: Dictionary containing information to add to the knowledge base
        """
        if isinstance(info, dict):
            self.knowledge.update(info)

    def get_behaviour_action_at(self, behaviour, action_index):
        """
        Get the action at the specified index in the specified behaviour.

        Args:
            behaviour: Name of the behaviour
            action_index: Index of the action within the behaviour

        Returns:
            The action at the specified index, or None if not found
        """
        found = None
        for beh in self.behaviours["behaviours"]:
            if behaviour == beh["name"]:
                found = beh
                break
        if found is None:
            logger.error("Unable to find behaviour %s", behaviour)
            return found
        if action_index < 0 or action_index >= len(found["actions"]):
            logger.error(
                "Invalid action index %d for behaviour %s", action_index, behaviour
            )
            return None
        return found["actions"][action_index]

    def rewind_activity(self):
        """
        Rewind to the previous activity.

        Decrements the activity index if not at the beginning and not busy.
        """
        if not self.active_behaviour:
            logger.error("No active behaviour. please check.")
            return
        # if self.activity_index == 0:
        if self.activity_index == -1:
            logger.info("We are at the beginning of the current behaviour.")
            return
        if self.is_busy():
            return
        self.activity_index = self.activity_index - 1

    def is_busy(self):
        """
        Check if the ActivityManager is currently busy.

        Returns:
            bool: True if there are running actions or actions lined up, False otherwise
        """
        return len(self.running_actions) > 0 or self.actions_lined_up

    def is_busy_after_suspension(self):
        """
        Check if the ActivityManager is busy after suspending suspendable actions.

        Suspends all suspendable custom actions and checks if still busy.

        Returns:
            bool: True if still busy after suspension, False otherwise
        """
        if len(self.running_actions) > 0:
            suspendable_objs = []
            for _, args in self.running_actions.items():
                if "_custom_obj" in args:  # a custom
                    obj = args["_custom_obj"]
                    if obj.is_suspendable():
                        suspendable_objs.append(obj)
            if len(self.running_actions) == len(
                suspendable_objs
            ):  # we can suspend all running customs
                logger.info("Suspend all suspendable custom actions")
                for obj in suspendable_objs:
                    obj.goto_suspension()
                self.suspended_actions = self.running_actions
                self.running_actions = {}
            else:
                logger.warning("All current running actions cannot be suspended.")
        return self.is_busy()

    async def play_next_activity_router(self, action_id="play_next"):
        """
        Route to the next activity.

        Checks if at the end of the active behaviour and calls the completion callback if so.
        Otherwise, sets continue_playing to True and plays the next activity.

        Args:
            action_id: Identifier for the action
        """
        # decide whether we should external message routing mechanism to
        # avoid callback stack message process delay due to calling play_behaviour
        # primitive that triggers from an earlier callback function.
        # check whether the upcoming action contains delay primitive
        if not self.active_behaviour:
            logger.warning("No active behaviour set")
            return

        if self.activity_index == len(self.active_behaviour) - 1:
            logger.debug("End of active behaviour")
            if self.activity_complete_cb is not None and callable(
                self.activity_complete_cb
            ):
                self.activity_complete_cb()
                self.activity_complete_cb = None
            return

        self.continue_playing = True
        action = self.active_behaviour[  # pylint: disable=unused-variable
            self.activity_index + 1
        ]
        # for alet in action:
        #    if alet[0] == 'delay':
        #        message = json.dumps({"node_id": "remote_control", "command":"right_no_suspension"})
        #        self.on_remote_play_next_activity = True
        #        return
        await self.play_next_activity(action_id=action_id)

    async def play_next_activity_with_suspension(self, suspend):
        """
        Play the next activity with a suspension time.

        Args:
            suspend: Time in seconds to suspend before playing the next activity
        """
        if not isinstance(suspend, int) or suspend <= 0:
            logger.error(
                "play_next_activityWithSuspension: suspension time must be a positive integer."
            )
            return

        await self.play_next_activity()

    async def play_next_activity_with_cb(self, cb):
        """
        Play the next activity with a completion callback.

        Args:
            cb: Callback function to be called when the activity completes
        """
        self.activity_complete_cb = cb
        await self.play_next_activity()

    async def play_next_activity(self, action_id="play_next", complete_cb=None):
        """
        Play the next activity in the active behaviour.

        Increments the activity index and plays the action at that index.

        Args:
            action_id: Identifier for the action
            complete_cb: Callback function to be called when the action completes.
                         This may be a regular function or a coroutine function.
                         If it's a coroutine function, it will be awaited.
        """
        self.on_remote_play_next_activity = False
        if self.is_busy():
            logger.warning(
                "Already playing actions - %s, running actions = %s",
                self.current_action_id,
                self.running_actions,
            )
            return

        if not self.active_behaviour:
            logger.warning("No active behaviour set")
            return

        if self.activity_index == len(self.active_behaviour) - 1:
            logger.debug("End of active behaviour")
            if self.activity_complete_cb is not None and callable(
                self.activity_complete_cb
            ):
                await self.activity_complete_cb()
                self.activity_complete_cb = None
            return

        self.set_activity_index(self.activity_index + 1)
        logger.debug("Playing Index - %d", self.activity_index)

        await self.play_action(
            action_id,
            self.active_behaviour[self.activity_index],
            complete_cb=complete_cb,
        )

    async def play_disruptive_action(
        self,
        action_id,
        action,
        action_type=None,
        complete_cb=None,
        external_notification_cb=None,
    ):
        """
        Play a disruptive action that clears any running actions first.

        Args:
            action_id: Identifier for the action
            action: Action to be executed
            action_type: Type of the action
            complete_cb: Callback function to be called when the action completes
            external_notification_cb: Callback function for external notification
        """
        if self.is_busy():
            self.clear_running_actions()
            logger.debug(
                "play_disruptive_action: Activity manager is busy, purge all running and pending actions for executing action - %s",
                action_id,
            )

        await self.play_action(
            action_id=action_id,
            action=action,
            complete_cb=complete_cb,
            external_notification_cb=external_notification_cb,
        )

    async def play_or_queue_disruptable_action(
        self,
        action_id,
        action,
        act_type=None,
        complete_cb=None,
        external_notification_cb=None,
    ):
        """
        Play or queue a disruptable action.

        Args:
            action_id: Identifier for the action
            action: Action to be executed
            act_type: Type of the action
            complete_cb: Callback function to be called when the action completes
            external_notification_cb: Callback function for external notification
        """
        await self.play_or_queue_action(
            action_id=action_id,
            action=action,
            action_type=act_type,
            complete_cb=complete_cb,
            external_notification_cb=external_notification_cb,
            is_disruptable=True,
        )

    async def play_or_queue_action(
        self,
        action_id,
        action,
        action_type=None,
        complete_cb=None,
        external_notification_cb=None,
        is_disruptable=False,
    ):
        """
        Play an action immediately or queue it if the system is busy.

        Args:
            action_id: Identifier for the action
            action: Action to be executed
            action_type: Type of the action
            complete_cb: Callback function to be called when the action completes
            external_notification_cb: Callback function for external notification
            is_disruptable: Whether this action can be disrupted by other actions
        """
        if self.is_busy_after_suspension():
            found = False
            for aid, _, _, _, _ in self.pending_actions:
                if aid == action_id:
                    found = True
                    break
            if not found:
                self.pending_actions += [
                    [
                        action_id,
                        action,
                        complete_cb,
                        external_notification_cb,
                        is_disruptable,
                    ]
                ]
                logger.warning(
                    "Activity manager is busy with %s, queued up the current action - %s",
                    self.running_actions,
                    action_id,
                )
        else:
            await self.play_action(
                action_id=action_id,
                action=action,
                complete_cb=complete_cb,
                external_notification_cb=external_notification_cb,
            )

    async def play_action(
        self,
        action_id,
        action,
        action_type=None,
        complete_cb=None,
        external_notification_cb=None,
        ignore_moves=[],
    ):
        """
        Play an action with the given ID and parameters.

        Executes each action element (alet) in the action list.

        Args:
            action_id: Identifier for the action
            action: List of action elements to execute
            action_type: Type of the action
            complete_cb: Callback function to be called when the action completes
            external_notification_cb: Callback function for external notification
            ignore_moves: List of action types to ignore

        Returns:
            bool: True if action was played successfully, False otherwise
        """
        if self.is_busy():
            logger.warning(
                "Already playing an action running_actions %s. ignore action %s",
                self.running_actions,
                action,
            )
            return False

        if complete_cb is not None:
            self.action_complete_cb = complete_cb

        if external_notification_cb is not None:
            self.external_notification_cb = external_notification_cb

        self.current_action_id = action_id
        logger.debug("Playing action with id - %s", self.current_action_id)
        for index, alet in enumerate(action):
            self.actions_lined_up = index != len(action) - 1
            if alet[0] == "name":
                logger.debug("Playing action %s(%s)", alet[1], action_id)
                # if the action_list is just [['name','ALIVE']], action_complete_cb will be called
                if index == len(action) - 1 and len(self.running_actions) == 0:
                    await self.on_action_completed(self.current_action_id)
            else:
                await self.play_action_let(alet, ignore_moves)

        return True

    async def play_action_let(
        self, alet, ignore_moves=[]
    ):  # pylint: disable=too-many-return-statements
        """
        Play a single action element (alet).

        Handles different types of action elements:
        - text: Send a text message
        - http_response: Send an HTTP response
        - knowledge: Update the knowledge base
        - comment: No-op with a comment
        - calculate: Perform a calculation
        - compare: Compare values
        - random: Select a random value
        - delay: Wait for a specified time
        - custom: Execute a custom behaviour
        - workflow_interaction: Set up workflow interaction actions
        - select_behaviour: Select a behaviour
        - play_behaviour: Play a behaviour

        Args:
            alet: Action element to execute
            ignore_moves: List of action types to ignore

        Note:
            For custom actions, module_arg can be None, which is handled by the custom behaviour class.
        """
        if len(alet) < 2:
            logger.error("Invalid alet %s", alet)
            return

        arg = alet[1]
        cmd = alet[0]

        if cmd == "custom":
            tag = arg["name"] if isinstance(arg, dict) else arg
        else:
            tag = cmd

        try:
            # if already running ignore
            if tag in self.running_actions:
                logger.warning(
                    "An existing %s is already executing, ignoring the new one-%s",
                    tag,
                    alet,
                )
                return
            else:
                self.running_actions[tag] = (
                    arg.copy() if isinstance(arg, dict) else {"name": arg}
                )
        except Exception as _:
            logger.error(
                "Not running %s, Something wrong with the args. Got %s", cmd, tag
            )
            return

        # set call backs if present
        if len(alet) > 2:
            if tag in self.chained_actions:
                self.chained_actions[tag].extend(alet[2:])
            else:
                self.chained_actions[tag] = alet[2:]

        logger.debug(
            "cmd = %s, arg = %s, to run = %s, chained_actions = %s",
            cmd,
            arg,
            tag,
            self.chained_actions,
        )

        if ignore_moves and cmd in ignore_moves:
            await self.actionFailHandler(cmd)
        elif cmd == "text":
            # there may be collision in key string with normal string
            # should enforce upcase for dict key.
            if isinstance(arg, str):
                if arg in self.knowledge:
                    arg = self.knowledge[arg]
            if isinstance(arg, list) and len(arg) == 2:
                sample = ["text", ["hello {}, good {}", ["KB_KEY1", "KB_KEY2"]]]
                keys = arg[1]
                if not isinstance(keys, list):
                    logger.error(
                        "Invalid alet(%s). action should of form-%s", alet, sample
                    )
                    await self.actionFailHandler(cmd)
                    return
                to_say = arg[0]
                for key in keys:
                    if key in self.knowledge:
                        to_say = to_say.replace("{}", str(self.knowledge[key]), 1)
                    else:
                        _key = str(key).replace("_", " ")
                        to_say = to_say.replace("{}", _key, 1)
            elif isinstance(arg, str):
                to_say = arg
            else:
                to_say = str(arg)
            try:
                status = 200
                lc_to_say = to_say.lower()
                if lc_to_say.startswith("unable") or lc_to_say.startswith("fail"):
                    logger.error("sending error message to user: %s", lc_to_say)
                    status = 400
                await self.send_message(status=status, data={"response": to_say})
                await self.actionHandler(cmd)
            except Exception as err:
                logger.error(
                    "unable to sending message to user: %s: %s", lc_to_say, err
                )
                await self.actionFailHandler(cmd)
        elif cmd == "http_response":
            if isinstance(arg, str):
                if arg in self.knowledge:
                    arg = self.knowledge[arg]
            if not isinstance(arg, dict):
                logger.error("Invalid alet(%s). Argument must be a dict", cmd)
                await self.actionFailHandler(cmd)
                return
            payload = json.loads(json.dumps(arg))
            for k, v in payload.items():
                if v in self.knowledge:
                    value = self.knowledge[v]
                    if isinstance(value, list) and len(value) > 1:
                        keys = value[1]
                        if not isinstance(keys, list):
                            logger.error(
                                "Invalid alet(%s): invalid payload: invalid composite value format",
                                cmd,
                            )
                            await self.actionFailHandler(cmd)
                            return
                        content = value[0]
                        for key in keys:
                            if key in self.knowledge:
                                content = content.replace(
                                    "{}", str(self.knowledge[key]), 1
                                )
                            else:
                                _key = str(key).replace("_", " ")
                                content = content.replace("{}", _key, 1)
                        payload[k] = content
                    else:
                        payload[k] = value
            if "status_code" not in payload or not isinstance(
                payload["status_code"], int
            ):
                logger.error(
                    "Invalid alet({cmd}): invalid payload: missing status code"
                )
                await self.actionFailHandler(cmd)
                return
            status_code = payload["status_code"]
            if "status" not in payload:
                if status_code < 200 or status_code >= 300:
                    payload["status"] = "success"
                else:
                    payload["status"] = "failed"
            del payload["status_code"]
            try:
                await self.send_raw_message(status_code, payload)
                await self.actionHandler(cmd)
            except Exception as _:
                await self.actionFailHandler(cmd)
        elif cmd == "knowledge":
            if isinstance(arg, dict):
                for k, v in arg.items():
                    if isinstance(v, str):
                        if v in self.knowledge:
                            self.knowledge.update(
                                {k: json.loads(json.dumps(self.knowledge[v]))}
                            )
                        else:
                            self.knowledge.update({k: v})
                    elif isinstance(v, list) and len(v) == 2 and isinstance(v[1], list):
                        keys = v[1]
                        content = v[0]
                        for key in keys:
                            if key in self.knowledge:
                                content = content.replace(
                                    "{}", str(self.knowledge[key]), 1
                                )
                            else:
                                _key = str(key).replace("_", " ")
                                content = content.replace("{}", _key, 1)
                        self.knowledge.update({k: content})
                    else:
                        self.knowledge.update({k: v})
                await self.actionHandler(cmd)
            else:
                logger.error("Cannot append knowledge, expected arg to be a dict")
                await self.actionFailHandler(cmd)
        elif cmd == "comment":  # comment does have a small performance impact
            await self.actionHandler(cmd)
        elif cmd == "calculate":
            # ['calculate', ['KB_KEY', '2*time+KB_KEY2']]
            # 'time' is UNIX time int(time.time())
            self.custom_behaviours["calculate"] = calculate(self.knowledge, *arg)
            self.custom_behaviours["calculate"].on_success = self.actionHandler
            self.custom_behaviours["calculate"].on_failure = self.actionFailHandler
            await self.custom_behaviours["calculate"].run()
        elif cmd == "compare":
            # ['compare', {
            #     'operand1':"time+KB_KEY1*23",
            #     'comparison_operator':'>',
            #     'operand2':'KB_KEY2*2+time',
            #     'true_action':['speech', 'the result is true'],
            #     'false_action':['speech', 'the result is false']
            # }]
            # 'time' is UNIX time int(time.time())
            self.custom_behaviours["compare"] = compare(self.knowledge, arg)
            self.custom_behaviours["compare"].on_success = self.actionHandler
            self.custom_behaviours["compare"].on_failure = self.actionFailHandler
            await self.custom_behaviours["compare"].run()
        elif cmd == "random":
            sample = ["random", ["KB_KEYNAME", [1, 2, 3]]]
            if isinstance(arg, list) and len(arg) == 2 and isinstance(arg[1], list):
                self.knowledge[arg[0]] = random.choice(arg[1])
                await self.actionHandler(cmd)
            else:
                logger.error(
                    "Invalid random action, should look like - %s, ignoring - %s",
                    sample,
                    alet,
                )
                await self.actionFailHandler(cmd)
        elif cmd == "delay":
            if isinstance(arg, int) or isinstance(arg, float) and arg > 0:
                await asyncio.sleep(arg)
                await self.actionHandler(cmd)
            else:
                logger.error("Invalid arg(%s) for delay, expected int/float > 0", arg)
                await self.actionFailHandler(cmd)
        elif cmd == "custom":
            if isinstance(arg, dict):
                module_name = arg["name"]
                if "args" in arg:
                    module_arg = arg["args"]
                    if not isinstance(module_arg, dict):
                        logger.error(
                            "Invalid alet(%s). Action arguments must be a dictionary",
                            alet,
                        )
                        await self.actionFailHandler(cmd)
                        return
                else:
                    module_arg = {}
            else:
                module_name = arg
                module_arg = None
            module = importlib.import_module("lurawi.custom." + module_name)
            importlib.reload(module)
            tclass = getattr(module, module_name)
            if issubclass(tclass, CustomBehaviour):
                self.custom_behaviours[module_name] = tclass(self.knowledge, module_arg)
                self.running_actions[module_name]["_custom_obj"] = (
                    self.custom_behaviours[module_name]
                )
                self.custom_behaviours[module_name].on_success = self.actionHandler
                self.custom_behaviours[module_name].on_failure = self.actionFailHandler
                await self.custom_behaviours[module_name].run()
            else:
                logger.warning(
                    "Custom script has to be an instance of CustomBehaviour. Ignoring %s",
                    alet,
                )
                await self.actionFailHandler(module_name)
        elif cmd == "workflow_interaction":
            if isinstance(arg, dict):
                if "engagement" in arg:
                    self.set_engagement_action(arg["engagement"])
                if "disengagement" in arg:
                    self.set_disengagement_action(arg["disengagement"])
                if "userdata" in arg:
                    self.set_user_data_action(arg["userdata"])
                await self.actionHandler(cmd)
            else:
                await self.actionFailHandler(cmd)
        elif cmd == "select_behaviour":
            if self.select_activity(arg):
                self.action_complete_cb = None
                await self.actionHandler(cmd)
            else:
                await self.actionFailHandler(cmd)
        elif cmd == "play_behaviour":
            if isinstance(arg, list):
                for let in arg:
                    if let[0] == "name":
                        continue
                    await self.play_action_let(let)
                await self.actionHandler(cmd)
            else:
                if self.select_activity(arg):
                    # we will close down all suspended actions when we jump behaviour regardless
                    if len(self.suspended_actions) > 0:
                        for name, arg in self.suspended_actions.items():
                            arg["_custom_obj"].fini()
                            del self.custom_behaviours[
                                name
                            ]  # delete from custom_behaviour
                        self.suspended_actions = {}

                    if len(self.pending_actions) > 0:
                        disrupt_action = None
                        for aid, act, ccb, encb, is_disruptable in self.pending_actions:
                            if is_disruptable:
                                disrupt_action = (aid, act, None, ccb, encb)
                                break

                        if disrupt_action is not None:
                            if self.knowledge["NO_DISRUPTION"]:
                                logger.warning(
                                    "play_behaviour: disruptable pending action, however we are in no disruption mode, continue current action and keep the queue"
                                )
                                self.action_complete_cb = self.play_next_activity_router
                            else:
                                logger.warning(
                                    "play_behaviour: only execute pending disruptable actions %d. purge all other pending action after current play_behaviour concludes",
                                    disrupt_action[0],
                                )
                                self.pending_actions = []
                                self.action_complete_cb = self.play_action
                                self.action_complete_cb_args = disrupt_action

                            await self.actionHandler(cmd)
                            return

                        logger.warning(
                            "play_behaviour: purge existing pending_actions %s",
                            self.pending_actions,
                        )
                        self.pending_actions = []

                    self.action_complete_cb = self.play_next_activity_router
                    await self.actionHandler(cmd)  # calling play_next_activity_router
                else:
                    await self.actionFailHandler(cmd)
        else:
            logger.error("unknown action - %s", alet)
            await self.actionFailHandler(cmd)

    async def actionHandler(self, action, data=None):
        """
        Handle the completion of an action.

        Cleans up the action, executes any chained actions, and calls the completion callback.

        Args:
            action: The action that completed
            data: Additional data for chained actions
        """
        if action not in self.running_actions:
            logger.error(
                "Running action(succeeded) error. Got %s, but running action = {self.running_actions.keys()}",
                action,
            )
            return

        # clean up the custom actions first
        if action in self.custom_behaviours:
            self.custom_behaviours[action].fini()
            del self.custom_behaviours[action]

        del self.running_actions[action]
        logger.debug(
            "Completed(succeeded) %s, running actions = %s",
            action,
            self.running_actions.keys(),
        )

        if data is not None:
            if action in self.chained_actions:
                self.chained_actions[action][0:0] = data
            else:
                self.chained_actions[action] = data

        if action in self.chained_actions:
            queued_action = self.chained_actions[action]
            del self.chained_actions[action]
            await self.play_action_let(queued_action)

        if not self.is_busy():
            logger.debug("Completed action with id - %s", self.current_action_id)
            self.chained_actions = {}
            await self.on_action_completed(self.current_action_id)

    async def actionFailHandler(self, action, data=None):
        """
        Handle the failure of an action.

        Cleans up the action, purges chained actions, and calls the completion callback.

        Args:
            action: The action that failed
            data: Additional data for failure handling
        """
        if action not in self.running_actions:
            logger.error(
                "Running action(failed) error. Got %s, but running actions = {self.running_actions.keys()}",
                action,
            )
            return

        if action in self.custom_behaviours:
            self.custom_behaviours[action].fini()
            del self.custom_behaviours[action]

        del self.running_actions[action]
        logger.error(
            "Completed(failed) %s, running actions = %s",
            action,
            self.running_actions.keys(),
        )

        # purge all left over actions
        if action in self.chained_actions:
            del self.chained_actions[action]

        # if any custom failure handling, run it
        if data is not None:
            await self.play_action_let(data)

        if not self.is_busy():
            logger.error(
                "Completed(failed) action with id - %s", self.current_action_id
            )
            self.chained_actions = {}
            await self.on_action_completed(self.current_action_id)

    def reset_running_actions(self):
        """
        Reset all running actions.

        Alias for clear_running_actions.
        """
        self.clear_running_actions()

    def clear_running_actions(self):
        """
        Clear all running actions, custom behaviours, and related state.

        Finalizes all custom behaviours and resets action-related state.
        """
        for beh in self.custom_behaviours.values():
            beh.fini()
        self.custom_behaviours = {}
        self.running_actions = {}
        self.chained_actions = {}
        self.pending_actions = []
        self.suspended_actions = (
            {}
        )  # suspended actions are all expected to be custom. They have been cleared above
        self.action_complete_cb = None
        self.activity_complete_cb = None
        self.actions_lined_up = False
        self.continue_playing = False
        self.knowledge["NO_DISRUPTION"] = 0

    async def on_action_completed(self, action_id=""):
        """
        Handle the completion of an action.

        Calls external notification callbacks, action completion callbacks,
        processes pending actions, and restores suspended actions.

        Note:
            This method handles callbacks that may be regular functions or coroutines.
            The external_notification_cb and action_complete_cb are expected to be
            compatible with the await syntax if they are called.

        Args:
            action_id: Identifier for the completed action
        """
        logger.debug(
            "on_action_completed: completed action %s Complete_cb = %s",
            action_id,
            self.action_complete_cb,
        )
        if self.external_notification_cb is not None and callable(
            self.external_notification_cb
        ):
            external_notification_cb = (
                self.external_notification_cb
            )  # short circuit recursive callback.
            self.external_notification_cb = None
            await external_notification_cb()

        if self.action_complete_cb is not None and callable(self.action_complete_cb):
            complete_cb = self.action_complete_cb  # short circuit recursive callback.
            self.action_complete_cb = None
            if self.action_complete_cb_args is not None:
                args = self.action_complete_cb_args  # must be a tuple
                self.action_complete_cb_args = None
                await complete_cb(*args)
            else:
                await complete_cb()

        if self.on_remote_play_next_activity:
            logger.warning(
                "on_action_completed: on remote play next activity, skip pending action"
            )
            return
        # Do the pending actions
        if len(self.pending_actions) > 0:
            (
                next_action_id,
                next_action,
                complete_cb,
                external_notification_cb,
                is_disruptable,  # pylint: disable=unused-variable
            ) = self.pending_actions[0]
            # NOTE is_disruptable is not used here. It is only used for play_behaviour logic
            logger.debug("start pending action - %s", next_action_id)
            if await self.play_action(
                "pending action-" + next_action_id,
                next_action,
                complete_cb=complete_cb,
                external_notification_cb=external_notification_cb,
            ):
                self.pending_actions = self.pending_actions[1:]
            else:
                logger.error(
                    "Unable to do pending action - %s. keep it in the queue",
                    next_action_id,
                )
        elif len(self.suspended_actions) > 0:
            for _, args in self.suspended_actions.items():
                args["_custom_obj"].restore_from_suspension()
            self.running_actions = (
                self.suspended_actions
            )  # reinsert into running actions
            self.suspended_actions = {}
            logger.debug(
                "on_action_completed: all current + queued actions are done, restore suspended custom actions"
            )
        else:
            logger.debug("on_action_completed: all current + queued actions are done.")
            if self.continue_playing:
                self.continue_playing = False
            elif self.activity_complete_cb is not None and callable(
                self.activity_complete_cb
            ):
                await self.activity_complete_cb()
                self.activity_complete_cb = None

    def on_shutdown(self):
        """
        Handle shutdown of the ActivityManager.

        Calls fini to clean up resources.
        """
        self.fini()

    async def on_update_user_data(self, data: Dict = {}):
        """
        Update user data with the given activity ID and data.

        Sets the user data in the knowledge base and plays the user data action if defined.

        Args:
            activity_id: Identifier for the activity
            data: Dictionary containing user data
        """
        if not data or not isinstance(data, dict):
            logger.error("missing or invalid user data %s", data)
            return

        if self.userdata_action:
            self.in_user_interaction = True
            await self.play_or_queue_action(
                "user_data",
                [self.userdata_action],
                external_notification_cb=self.user_data_complete,
            )

    def check_remote_callback_access(self, access_key: str):
        """
        Check if the access key matches the current turn context.

        Args:
            access_key: Key to check against the current turn context

        Returns:
            bool: True if the access key matches, False otherwise
        """
        return access_key == self.knowledge["CURRENT_TURN_CONTEXT"]

    async def process_remote_callback_payload(self, method: str, data: Dict):
        """
        Process a remote callback payload.

        Delegates to the callback message manager.

        Args:
            method: Method name for the callback
            data: Dictionary containing callback data
        """
        await self.callbackmessage_manager.process_remote_callback_messages(
            method=method, message=data
        )

    async def send_message(
        self, status: int = 200, data: Dict | DataStreamHandler = {}, headers: Dict = {}
    ):
        """
        Send a message to the user.

        Handles different types of responses:
        - StreamingResponse for DataStreamHandler
        - Discord messages for DiscordMessage context
        - HTTP responses for other contexts

        Args:
            status: HTTP status code
            data: Response data or stream handler
            headers: HTTP headers
        """
        context = self.knowledge["CURRENT_TURN_CONTEXT"]
        if not self._agent_mode:
            if isinstance(data, DataStreamHandler):
                headers.update({"X-Accel-Buffering": "no"})
                self.response = StreamingResponse(
                    data.stream_generator(),
                    headers=headers,
                    media_type="text/event-stream",
                )
                return

            if self._discord_message is None:
                try:
                    from discord import (  # pylint: disable=import-outside-toplevel
                        Message as DiscordMessage,
                    )

                    self._discord_message = DiscordMessage
                except ImportError:
                    logger.error("Unable to import DiscordMessage")
            if isinstance(context, self._discord_message):
                # a single discord message cannot be longer than 2000
                out_text = data["response"]
                while len(out_text) > 1800:
                    await context.channel.send(out_text[:1800])
                    await asyncio.sleep(0.01)
                    out_text = out_text[1801:]
                await context.channel.send(out_text)
                return

        status_msg = "success"
        if status < 200 or status >= 300:
            status_msg = "failed"

        payload = {
            "status": status_msg,
            "activity_id": context,
        }
        payload.update(data)

        if self.knowledge["CURRENT_SESSION_ID"]:
            payload["session_id"] = self.knowledge["CURRENT_SESSION_ID"]

        self.response = write_http_response(status, payload, headers=headers)

    async def send_raw_message(self, status, payload, headers: Dict = {}):
        """
        Send a raw message with the given status and payload.

        Adds the activity ID to the payload and writes an HTTP response.

        Args:
            status: HTTP status code
            payload: Response payload
            headers: HTTP headers
        """
        payload["activity_id"] = self.knowledge["CURRENT_TURN_CONTEXT"]
        self.response = write_http_response(status, payload, headers=headers)

    async def execute_behaviour(self, behaviour, knowledge={}):
        """
        Execute a behaviour with the given knowledge.

        Updates the knowledge base and plays or queues the behaviour.

        Args:
            behaviour: Behaviour to execute
            knowledge: Dictionary containing knowledge to update
        """
        self.knowledge.update(knowledge)
        if behaviour in self.knowledge:
            behaviour = self.knowledge[behaviour]
        print(f"play queue behaviour {behaviour}")
        await self.play_or_queue_action(
            "manual_execution", [["play_behaviour", behaviour]]
        )

    def get_response(self):
        """
        Get the current response.

        Resets the in_user_interaction flag and returns the response.
        If no response is available, returns a 406 error.

        Returns:
            The current response or a 406 error response
        """
        response = None
        self.in_user_interaction = False
        if self.response is None:
            return JSONResponse(
                status_code=406,
                content={
                    "status": "failed",
                    "activity_id": self.knowledge["CURRENT_TURN_CONTEXT"],
                    "response": "I'm unable to process your question.",
                },
            )
        else:
            response = self.response
            self.response = None
        return response

    def idleTime(self):
        """
        Get the idle time of the ActivityManager.

        Returns:
            float: Time in seconds since the last access
        """
        return time.time() - self.access_time

    def fini(self):
        """
        Finalize the ActivityManager.

        Cleans up running actions and finalizes message managers.
        """
        self.clear_running_actions()
        self.usermessage_manager.fini()
        self.callbackmessage_manager.fini()
