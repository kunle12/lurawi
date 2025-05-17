import boto3
import importlib
import inspect
import os
import simplejson as json
import time

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobClient
from discord import Message as DiscordMessage
from fastapi import Depends
from fastapi.responses import JSONResponse
from io import StringIO
from pydantic import BaseModel, Extra
from threading import Lock as mutex
from typing import Dict, Any

from .activity_manager import ActivityManager
from .remote_service import RemoteService
from .timer_manager import TimerClient, timerManager
from .utils import logger, api_access_check, write_http_response

STANDARD_LURAWI_CONFIGS = [
    "PROJECT_NAME",
    "PROJECT_ACCESS_KEY",
]


class WorkflowInputPayload(BaseModel, extra=Extra.allow):
    uid: str
    name: str
    session_id: str = ""
    activity_id: str = ""
    data: Dict[str, Any] = None

    @property
    def extra_fields(self) -> set[str]:
        return set(self.__dict__) - set(self.model_fields)


class BehaviourCodePayload(BaseModel):
    jsonCode: str
    xmlCode: str = ""
    toSave: bool = False


class WorkflowEngine(TimerClient):
    """ """

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
                    f"load_knowledge: no knowledge file {kbase} is provided."
                )
                return True
        except ResourceNotFoundError:
            logger.warning(f"load_knowledge: no knowledge file {kbase} is provided.")
            return True
        except Exception as err:
            logger.error(
                f"load_knowledge: unable to load knowledge file '{kbase_path}' from blob storage:{err}"
            )
            return False

        self.knowledge.update(json_data)

        # load any standard environmental variables overwrite
        # the existing knowledge.
        for config in STANDARD_LURAWI_CONFIGS:
            if config in os.environ:
                self.knowledge[config] = os.environ[config]

        logger.info(f"load_knowledge: Knowledge file {kbase_path} is loaded!")

        # check for custom domain specific language analysis model
        return True

    def load_behaviours(self, behaviour=""):
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
                    f"load_behaviours: no custom behaviour file {behaviour_file} is provided."
                )
                return loaded_behaviours
        except Exception as err:
            logger.error(f"Cannot load behaviours {behaviour_file}, Exception-{err}")
            return loaded_behaviours

        if "default" not in loaded_behaviours:
            logger.error("missing default in custom behaviour file {behaviour_file}")
            return loaded_behaviours

        self.custom_behaviour = behaviour

        if not self.load_knowledge(behaviour + "_knowledge"):
            logger.info("No custom knowledge for new behaviours is loaded")

        logger.info(f"load_behaviours: behaviours file {behaviour_file} is loaded!")
        return loaded_behaviours

    def load_pending_behaviours(self, behaviour):
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
        discord_id = message.author.id
        self._mutex.acquire()
        if discord_id in self.conversation_members:
            activity_manager = self.conversation_members[discord_id]
            self._mutex.release()
            await activity_manager.updateTurnContext(context=message)
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
            await activity_manager.startUserEngagement(context=message)

    async def on_event(
        self,
        payload: WorkflowInputPayload,
        authorised: bool = Depends(api_access_check),
    ):
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
            response = await activity_manager.continueWorkflow(
                activity_id=payload.activity_id, data=payload.data
            )
        else:
            response = await activity_manager.startUserWorkflow(
                session_id=payload.session_id, data=payload.data
            )
        if response:
            return activity_manager.getResponse()
        else:
            return JSONResponse(
                status_code=429,
                content={
                    "status": "failed",
                    "message": "System is busy, please try later.",
                },
            )

    async def on_code_update(self, payload: BehaviourCodePayload):
        loaded_behaviours = {}
        try:
            loaded_behaviours = json.loads(payload.jsonCode)
        except Exception as err:
            logger.error(f"Cannot load code update: {err}")
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
        if uid in self.conversation_members:
            return self.conversation_members[uid]
        return None

    async def on_executing_behaviour_for_uid(
        self, uid: str, behaviour: str, knowledge: Dict = {}
    ) -> bool:
        if uid in self.conversation_members:
            activity_manager = self.conversation_members[uid]
            return await activity_manager.executeBehaviour(behaviour, knowledge)

        logger.error(f"unable to find uid {uid} for behaviour execution")
        return False

    async def health_check(self):
        result = "Welcome to the HealthCheck Service!"
        return JSONResponse(
            status_code=200, content={"status": "success", "result": result}
        )

    def on_shutdown(self):
        timerManager.fini()

        for member in self.conversation_members.values():
            member.onShutdown()
        self.stop_remote_services()

    async def on_pending_load_complete(self):
        if self.pending_behaviours_load_cnt == 0:
            return

        self.pending_behaviours_load_cnt -= 1
        if self.pending_behaviours_load_cnt == 0:
            logger.info("pending behaviours are fully loaded by members")
            self.behaviours = self.pending_behaviours
            self.pending_behaviours = {}

    async def on_timer(self, tid):
        if self.auto_purge_timer == tid:
            logger.info("checking current online users status, auto purge idle users.")
            await self.purge_idle_users()

    async def purge_idle_users(self):
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
        self.remote_services = []
        for _, _, files in os.walk("lurawi/services"):
            for f in files:
                if f.endswith(".py") and f != "__init__.py":
                    mpath = "lurawi.services." + os.path.splitext(f)[0]
                    try:
                        m = importlib.import_module(mpath)
                    except Exception as err:
                        logger.error(
                            f"Unable to import service module script {f}: {err}"
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
                                    logger.info(f"{name} service is initialised.")
                            except Exception as err:
                                logger.error(f"Unable to load {name} service: {err}.")

    def fini_remote_services(self):
        for s in self.remote_services:
            s.fini()
        self.remote_services = []

    def start_remote_services(self):
        for s in self.remote_services:
            s.start()

    def stop_remote_services(self):
        for s in self.remote_services:
            s.stop()
