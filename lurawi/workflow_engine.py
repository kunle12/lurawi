"""Workflow Engine for Lurawi.

This module implements the core workflow engine that powers the Lurawi system.
It provides functionality for:
- Managing user conversations and activities
- Loading and executing behaviors from configuration files
- Handling events from various sources (Discord, API calls)
- Managing knowledge bases for behaviors
- Dynamically loading and managing remote services
- Supporting timer-based operations

The WorkflowEngine class serves as the central coordinator for all these
activities, maintaining conversation state, loading behaviors and knowledge,
and routing events to appropriate handlers.
"""

import importlib
import inspect
import time
import os

from io import StringIO
from threading import Lock as mutex
from typing import Dict, Any

import simplejson as json
import boto3

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobClient
from discord import Message as DiscordMessage
from fastapi import Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Extra

from .activity_manager import ActivityManager
from .remote_service import RemoteService
from .timer_manager import TimerClient, timerManager
from .utils import logger, api_access_check, write_http_response

STANDARD_LURAWI_CONFIGS = [
    "PROJECT_NAME",
    "PROJECT_ACCESS_KEY",
]


class WorkflowInputPayload(BaseModel, extra=Extra.allow):
    """Payload model for workflow input data.

    This model defines the structure of input data required to trigger
    a workflow in the system. It allows for extra fields beyond those
    explicitly defined.
    """

    uid: str  # Unique identifier for the user/entity
    name: str  # Name of the user/entity
    session_id: str = ""  # Optional session identifier
    activity_id: str = ""  # Optional activity identifier
    data: Dict[str, Any] = {}  # Additional data payload

    @property
    def extra_fields(self) -> set[str]:
        """Returns a set of field names that are not part of the model's defined fields.

        Returns:
            set[str]: Set of extra field names present in the instance
        """
        return set(self.__dict__) - set(self.model_fields)


class BehaviourCodePayload(BaseModel):
    """Payload model for behavior code updates.

    This model defines the structure for updating behavior code in the system,
    supporting both JSON and XML formats.
    """

    jsonCode: str  # JSON representation of the behavior code
    xmlCode: str = ""  # Optional XML representation of the behavior code
    toSave: bool = False  # Flag indicating whether to save the code


class WorkflowEngine(TimerClient):
    """Workflow engine that manages user interactions, behaviors, and remote services.

    This class is the core engine that handles workflow execution, user activity management,
    behavior loading, and integration with remote services. It inherits from TimerClient
    to support scheduled operations.
    """

    def __init__(self, custom_behaviour: str) -> None:
        super(WorkflowEngine, self).__init__()
        self.startup_time = time.time()

        self.conversation_members = {}

        self.knowledge = {}
        self.load_knowledge("default_knowledge")

        self.custom_behaviour = custom_behaviour
        self.behaviours = self.load_behaviours(custom_behaviour)
        self.pending_behaviours = {}
        self.pending_behaviours_load_cnt = 0
        # self.onceoff_startup_timer = timerManager.add_timer(self, init_start=2, interval=0, repeats=0)
        # self.auto_save_log_timer = timerManager.add_timer(self, init_start=1800, interval=1800)
        self.auto_purge_timer = None

        if (
            "AutoPurgeIdleUsers" in os.environ
            and os.environ["AutoPurgeIdleUsers"] == "1"
        ):
            self.auto_purge_timer = timerManager.add_timer(
                self, init_start=3600, interval=3600
            )
        self._mutex = mutex()
        self._init_remote_services()
        self.start_remote_services()

    def load_knowledge(self, kbase: str) -> bool:
        """Load knowledge base from a JSON file.

        Attempts to load knowledge from various sources in the following order:
        1. Azure Blob Storage (if AzureWebJobsStorage is configured)
        2. AWS S3 (if AWS credentials are configured)
        3. Local file system at various paths

        Args:
            kbase: Base name of the knowledge file (without extension)

        Returns:
            bool: True if knowledge was loaded successfully or if file was not found,
                  False if there was an error loading the file
        """
        kbase_path = kbase + ".json"
        try:
            if "AzureWebJobsStorage" in os.environ:
                connect_string = os.environ["AzureWebJobsStorage"]
                blob = BlobClient.from_connection_string(
                    conn_str=connect_string,
                    container_name="lurawidata",
                    blob_name=kbase_path,
                )
                json_data = json.loads(blob.download_blob().content_as_text())
            elif (
                "UseAWSS3" in os.environ
                and "AWS_ACCESS_KEY_ID" in os.environ
                and "AWS_SECRET_ACCESS_KEY" in os.environ
            ):
                s3_client = boto3.client("s3")
                blobio = StringIO()
                s3_client.download_fileobj("lurawidata", kbase_path, blobio)
                json_data = json.loads(blobio.read())
            elif os.path.exists(kbase_path):
                with open(kbase_path) as data:
                    json_data = json.load(data)
            elif os.path.exists(f"/home/lurawi/{kbase_path}"):
                with open(f"/home/lurawi/{kbase_path}") as data:
                    json_data = json.load(data)
            elif os.path.exists(f"/opt/defaultsite/{kbase_path}"):
                with open(f"/opt/defaultsite/{kbase_path}") as data:
                    json_data = json.load(data)
            else:
                logger.warning(
                    "load_knowledge: no knowledge file %s is provided.", kbase
                )
                return True
        except ResourceNotFoundError:
            logger.warning("load_knowledge: no knowledge file %s is provided.", kbase)
            return True
        except Exception as err:
            logger.error(
                "load_knowledge: unable to load knowledge file %s from blob storage:%s",
                kbase_path,
                err,
            )
            return False

        self.knowledge.update(json_data)

        # load any standard environmental variables overwrite
        # the existing knowledge.
        for config in STANDARD_LURAWI_CONFIGS:
            if config in os.environ:
                self.knowledge[config] = os.environ[config]

        logger.info("load_knowledge: Knowledge file %s is loaded!", kbase_path)

        # check for custom domain specific language analysis model
        return True

    def load_behaviours(self, behaviour=""):
        """Load behaviors from a JSON file.

        Attempts to load behaviors from various sources in the following order:
        1. Azure Blob Storage (if AzureWebJobsStorage is configured)
        2. AWS S3 (if AWS credentials are configured)
        3. Local file system at various paths

        Args:
            behaviour: Base name of the behavior file (without extension)

        Returns:
            dict: Dictionary containing loaded behaviors, or empty dict if loading failed
        """
        loaded_behaviours = {}
        if not behaviour:
            if self.custom_behaviour:
                behaviour = self.custom_behaviour
            else:
                logger.error("load_behaviours: no behaviour file provided")
                return loaded_behaviours

        if behaviour.endswith(".json"):
            logger.warning("load_behaviours: extension .json is not required")
            return loaded_behaviours

        behaviour_file = behaviour + ".json"

        try:
            if "AzureWebJobsStorage" in os.environ:
                connect_string = os.environ["AzureWebJobsStorage"]
                blob = BlobClient.from_connection_string(
                    conn_str=connect_string,
                    container_name="lurawidata",
                    blob_name=behaviour_file,
                )
                loaded_behaviours = json.loads(blob.download_blob().content_as_text())
            elif (
                "AWS_ACCESS_KEY_ID" in os.environ
                and "AWS_SECRET_ACCESS_KEY" in os.environ
            ):
                s3_client = boto3.client("s3")
                blobio = StringIO()
                s3_client.download_fileobj("lurawidata", behaviour_file, blobio)
                loaded_behaviours = json.loads(blobio.read())
            elif os.path.exists(behaviour_file):
                with open(behaviour_file) as data:
                    loaded_behaviours = json.load(data)
            elif os.path.exists(f"/home/lurawi/{behaviour_file}"):
                with open(f"/home/lurawi/{behaviour_file}") as data:
                    loaded_behaviours = json.load(data)
            elif os.path.exists(f"/opt/defaultsite/{behaviour_file}"):
                with open(f"/opt/defaultsite/{behaviour_file}") as data:
                    loaded_behaviours = json.load(data)
            else:
                logger.error(
                    "load_behaviours: no custom behaviour file %s is provided.",
                    behaviour_file,
                )
                return loaded_behaviours
        except Exception as err:
            logger.error("Cannot load behaviours %s, %s", behaviour_file, err)
            return loaded_behaviours

        if "default" not in loaded_behaviours:
            logger.error("missing default in custom behaviour file {behaviour_file}")
            return loaded_behaviours

        self.custom_behaviour = behaviour

        if not self.load_knowledge(behaviour + "_knowledge"):
            logger.info("No custom knowledge for new behaviours is loaded")

        logger.info("load_behaviours: behaviours file %s is loaded!", behaviour_file)
        return loaded_behaviours

    def load_pending_behaviours(self, behaviour):
        """Load behaviors into a pending state for gradual adoption.

        Loads behaviors into a pending state and notifies conversation members
        to prepare for the behavior change. When all members have acknowledged,
        the pending behaviors become active.

        Args:
            behaviour: Base name of the behavior file to load

        Returns:
            str: Status message indicating success or failure
        """
        self.pending_behaviours = self.load_behaviours(behaviour)
        self.pending_behaviours_load_cnt = len(self.conversation_members)
        if self.pending_behaviours:
            if self.pending_behaviours_load_cnt > 0:
                for member in self.conversation_members.values():
                    member.setPendingBehaviours(
                        self.pending_behaviours,
                        self.knowledge,
                        self.on_pending_load_complete,
                    )
            else:
                self.behaviours = self.pending_behaviours
                self.pending_behaviours = {}
            replymsg = "New Bot behaviours have been reloaded."
        else:
            replymsg = "New Bot behaviours is corrupted, ignore."
        return replymsg

    async def on_discord_event(self, user_name: str, message: DiscordMessage):
        """Handle incoming Discord events.

        Processes Discord messages by either updating an existing conversation
        or creating a new one for the user.

        Args:
            user_name: Name of the Discord user
            message: Discord message object containing the event data
        """
        discord_id = message.author.id
        self._mutex.acquire()
        if discord_id in self.conversation_members:
            activity_manager = self.conversation_members[discord_id]
            self._mutex.release()
            await activity_manager.update_turn_context(context=message)
        else:
            if self.pending_behaviours:
                activity_manager = ActivityManager(
                    discord_id, user_name, self.pending_behaviours, self.knowledge
                )
            else:
                activity_manager = ActivityManager(
                    discord_id, user_name, self.behaviours, self.knowledge
                )
            self.conversation_members[discord_id] = activity_manager
            self._mutex.release()
            await activity_manager.init()
            await activity_manager.start_user_engagement(context=message)

    async def on_event(
        self,
        payload: WorkflowInputPayload,
        authorised: bool = Depends(api_access_check),
    ):
        """Handle incoming workflow events.

        Processes workflow events by either continuing an existing workflow
        or starting a new one based on the payload.

        Args:
            payload: Input data for the workflow
            authorised: Flag indicating if the request is authorized

        Returns:
            Response object with workflow results or error message
        """
        if not authorised:
            return write_http_response(
                401, {"status": "failed", "message": "Unauthorised access."}
            )

        memberid = payload.uid
        self._mutex.acquire()
        if memberid in self.conversation_members:
            activity_manager = self.conversation_members[memberid]
            self._mutex.release()
        else:
            if self.pending_behaviours:
                activity_manager = ActivityManager(
                    memberid, payload.name, self.pending_behaviours, self.knowledge
                )
            else:
                activity_manager = ActivityManager(
                    memberid, payload.name, self.behaviours, self.knowledge
                )
            self.conversation_members[memberid] = activity_manager
            self._mutex.release()
            await activity_manager.init()

        response = False
        if payload.activity_id:
            response = await activity_manager.continue_workflow(
                activity_id=payload.activity_id, data=payload.data
            )
        else:
            response = await activity_manager.start_user_workflow(
                session_id=payload.session_id, data=payload.data
            )
        if response:
            return activity_manager.get_response()
        else:
            return JSONResponse(
                status_code=429,
                content={
                    "status": "failed",
                    "message": "System is busy, please try later.",
                },
            )

    async def on_code_update(self, payload: BehaviourCodePayload):
        """Update behavior code dynamically.

        Updates the behavior code with the provided JSON code, purging all
        existing users to ensure clean adoption of the new behaviors.

        Args:
            payload: Behavior code payload containing JSON and XML code

        Returns:
            HTTP response indicating success or failure
        """
        loaded_behaviours = {}
        try:
            loaded_behaviours = json.loads(payload.jsonCode)
        except Exception as err:
            logger.error("Cannot load code update: %s", err)
            return write_http_response(
                400, {"status": "failed", "message": "unable to load code updates."}
            )

        if "default" not in loaded_behaviours:
            logger.error("missing default in code update")
            return write_http_response(
                400, {"status": "failed", "message": "missing default in code updates."}
            )
        logger.info("on_code_update: purging all existing users.")
        self._mutex.acquire()

        for member in self.conversation_members.values():
            member.fini()
        self.conversation_members = {}
        self._mutex.release()
        self.behaviours = loaded_behaviours

        return write_http_response(200, {"status": "success"})

    def get_member(self, uid: str) -> ActivityManager | None:
        """Retrieve a conversation member by user ID.

        Args:
            uid: User ID to look up

        Returns:
            ActivityManager for the user if found, None otherwise
        """
        if uid in self.conversation_members:
            return self.conversation_members[uid]
        return None

    async def on_executing_behaviour_for_uid(
        self, uid: str, behaviour: str, knowledge: Dict = {}
    ) -> bool:
        """Execute a specific behavior for a given user.

        Args:
            uid: User ID to execute the behavior for
            behaviour: Name of the behavior to execute
            knowledge: Additional knowledge to provide to the behavior

        Returns:
            bool: True if behavior was executed successfully, False otherwise
        """
        if uid in self.conversation_members:
            activity_manager = self.conversation_members[uid]
            return await activity_manager.execute_behaviour(behaviour, knowledge)

        logger.error("unable to find uid %s for behaviour execution", uid)
        return False

    async def health_check(self):
        """Perform a health check on the workflow engine.

        Returns:
            JSONResponse with status information
        """
        result = "Welcome to the HealthCheck Service!"
        return JSONResponse(
            status_code=200, content={"status": "success", "result": result}
        )

    def on_shutdown(self):
        """Clean up resources when the workflow engine is shutting down.

        Finalizes the timer manager, notifies all conversation members of shutdown,
        and stops all remote services.
        """
        timerManager.fini()

        for member in self.conversation_members.values():
            member.on_shutdown()
        self.stop_remote_services()

    async def on_pending_load_complete(self):
        """Handle completion of pending behavior loading.

        Called when a conversation member completes loading pending behaviors.
        When all members have completed loading, the pending behaviors become active.
        """
        if self.pending_behaviours_load_cnt == 0:
            return

        self.pending_behaviours_load_cnt -= 1
        if self.pending_behaviours_load_cnt == 0:
            logger.info("pending behaviours are fully loaded by members")
            self.behaviours = self.pending_behaviours
            self.pending_behaviours = {}

    async def on_timer(self, tid):
        """Handle timer events.

        Called when a timer fires. Handles different timer types based on the timer ID.

        Args:
            tid: Timer ID that triggered this event
        """
        if self.auto_purge_timer == tid:
            logger.info("checking current online users status, auto purge idle users.")
            await self.purge_idle_users()

    async def purge_idle_users(self):
        """Remove idle users from the conversation members.

        Identifies users who have been idle for more than 2400 seconds (40 minutes)
        and removes them from the active conversation members list.
        """
        idle_users = []
        self._mutex.acquire()
        for mid, member in self.conversation_members.items():
            if member.idleTime() > 2400:
                idle_users.append(mid)

        for mid in idle_users:
            self.conversation_members[mid].fini()
            del self.conversation_members[mid]
        self._mutex.release()

    def _init_remote_services(self):
        """Initialize remote services from the services directory.

        Dynamically loads and initializes all remote service modules found in
        the lurawi/services directory.
        """
        self.remote_services = []
        for _, _, files in os.walk("lurawi/services"):
            for f in files:
                if f.endswith(".py") and f != "__init__.py":
                    mpath = "lurawi.services." + os.path.splitext(f)[0]
                    try:
                        m = importlib.import_module(mpath)
                    except Exception as err:
                        logger.error(
                            "Unable to import service module script %s: %s", f, err
                        )
                        continue
                    for name, objclass in inspect.getmembers(m, inspect.isclass):
                        if (
                            issubclass(objclass, RemoteService)
                            and name != "RemoteService"
                        ):
                            try:
                                obj = objclass(owner=self)
                                if obj.init():
                                    self.remote_services.append(obj)
                                    logger.info("%s service is initialised.", name)
                            except Exception as err:
                                logger.error(
                                    "Unable to load %s service: %s.", name, err
                                )

    def fini_remote_services(self):
        """Finalize all remote services.

        Calls the fini method on all remote services and clears the services list.
        """
        for s in self.remote_services:
            s.fini()
        self.remote_services = []

    def start_remote_services(self):
        """Start all initialized remote services.

        Calls the start method on all remote services.
        """
        for s in self.remote_services:
            s.start()

    def stop_remote_services(self):
        """Stop all running remote services.

        Calls the stop method on all remote services.
        """
        for s in self.remote_services:
            s.stop()
