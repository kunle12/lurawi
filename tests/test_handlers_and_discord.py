"""Tests for the webhook handlers and the Discord messenger wrapper."""

import asyncio

from lurawi.handlers.get_conversation_stream import GetConversationStream
from lurawi.handlers.remote_service_notification import (
    RemoteServiceNotificationHandler,
    RemoteServiceNotificationPayload,
)
from lurawi.handlers.system_operations import SystemOperationPayload, SystemOperationsHandler
from lurawi.services.discord_messenger import DiscordMessenger, HomeBot
from lurawi.utils import get_dev_stream_handler, set_dev_stream_handler


class FakeServer:
    def __init__(self):
        self.knowledge = {}
        self.members = {}

    def get_member(self, uid):
        return self.members.get(uid)

    def load_pending_behaviours(self, behaviour):
        return f"loaded {behaviour}"


class FakeMember:
    def __init__(self, access_ok=True):
        self.access_ok = access_ok
        self.processed = []

    def check_remote_callback_access(self, key):
        return self.access_ok

    async def process_remote_callback_payload(self, method, data):
        self.processed.append((method, data))


# ---- system_operations ----


def test_system_operations_disabled(monkeypatch):
    monkeypatch.delenv("BackendOperationEnabled", raising=False)
    h = SystemOperationsHandler(FakeServer())
    assert h.is_disabled is True


def test_system_operations_process(monkeypatch):
    monkeypatch.setenv("BackendOperationEnabled", "1")
    monkeypatch.setenv("SystemAdminKey", "admin")
    h = SystemOperationsHandler(FakeServer())
    assert h.is_disabled is False
    # missing SystemAdminKey
    monkeypatch.delenv("SystemAdminKey", raising=False)
    resp = asyncio.run(h.process_callback(SystemOperationPayload(admin_key="a", command="load")))
    assert resp.status_code == 400
    # wrong key
    monkeypatch.setenv("SystemAdminKey", "admin")
    resp = asyncio.run(
        h.process_callback(SystemOperationPayload(admin_key="wrong", command="load"))
    )
    assert resp.status_code == 400
    # correct key + load
    resp = asyncio.run(
        h.process_callback(SystemOperationPayload(admin_key="admin", command="load", value="pb"))
    )
    assert resp.status_code == 200
    assert b"loaded pb" in resp.body


# ---- remote_service_notification ----


def test_remote_notification_init(monkeypatch):
    monkeypatch.setenv("RemoteWebhookURL", "http://localhost:8081")
    server = FakeServer()
    RemoteServiceNotificationHandler(server)
    assert server.knowledge["REMOTE_CALLBACK_URL"] == "http://localhost:8081/remote_callback"


def test_remote_notification_process(monkeypatch):
    monkeypatch.setenv("RemoteWebhookURL", "http://localhost:8081")
    server = FakeServer()
    server.knowledge["REMOTE_CALLBACK_URL"] = "x"
    h = RemoteServiceNotificationHandler(server)
    # unknown member -> 400
    resp = asyncio.run(
        h.process_callback(
            RemoteServiceNotificationPayload(
                success=True, access_key="k", uid="nope", method="m", data={}
            )
        )
    )
    assert resp.status_code == 400
    # member exists but wrong access key -> 400
    member = FakeMember(access_ok=False)
    server.members["u1"] = member
    resp = asyncio.run(
        h.process_callback(
            RemoteServiceNotificationPayload(
                success=True, access_key="k", uid="u1", method="m", data={}
            )
        )
    )
    assert resp.status_code == 400
    # success -> processes
    member2 = FakeMember(access_ok=True)
    server.members["u2"] = member2
    resp = asyncio.run(
        h.process_callback(
            RemoteServiceNotificationPayload(
                success=True, access_key="k", uid="u2", method="m", data={"a": 1}
            )
        )
    )
    assert resp.status_code == 200
    assert member2.processed == [("m", {"a": 1})]
    # failure -> does not process but returns 200
    member3 = FakeMember(access_ok=True)
    server.members["u3"] = member3
    resp = asyncio.run(
        h.process_callback(
            RemoteServiceNotificationPayload(
                success=False, access_key="k", uid="u3", method="m", data={}
            )
        )
    )
    assert resp.status_code == 200
    assert member3.processed == []


# ---- get_conversation_stream ----


def test_get_conversation_stream_disabled(monkeypatch):
    monkeypatch.setattr("lurawi.utils.in_dev", False)
    h = GetConversationStream()
    assert h.is_disabled is True


def test_get_conversation_stream_process(monkeypatch):
    monkeypatch.setattr("lurawi.utils.in_dev", True)
    h = GetConversationStream()
    # no stream -> 404
    resp = asyncio.run(h.process_callback())
    assert resp.status_code == 404

    # with a stream handler -> StreamingResponse
    async def gen():
        yield "data: hi\n\n"

    handler = type("H", (), {"stream_generator": staticmethod(gen)})()
    set_dev_stream_handler(handler)
    resp = asyncio.run(h.process_callback())
    assert resp.status_code == 200
    assert get_dev_stream_handler() is None
    set_dev_stream_handler(None)


# ---- DiscordMessenger / HomeBot ----


def test_discord_messenger_init_no_token(monkeypatch):
    monkeypatch.delenv("DiscordToken", raising=False)
    server = FakeServer()
    server.knowledge = {}
    owner = type("O", (), {"knowledge": server.knowledge})()
    dm = DiscordMessenger(owner)
    assert dm.init() is False


def test_discord_messenger_init_with_token_and_start():
    server = FakeServer()
    server.knowledge = {"DiscordToken": "fake-token"}
    owner = type("O", (), {"knowledge": server.knowledge})()
    dm = DiscordMessenger(owner)
    assert dm.init() is True
    assert dm.client is not None
    # not running -> send returns False
    assert dm.send_message_to_user("u", "hi") is False
    # start when not running but client exists -> would connect, so mock it
    dm.client.start_running = lambda: None
    dm.start()
    assert dm.is_running is True
    dm.stop()
    assert dm.is_running is False
    dm.fini()
    assert dm.is_initialised is False


def test_homebot_name_mapping():
    server = FakeServer()
    server.knowledge = {"DiscordUserMap": {"123": "alice"}}
    owner = type("O", (), {"knowledge": server.knowledge})()
    bot = HomeBot(owner)
    assert bot._discord_name_to_user("alice") == "123"
    assert bot._discord_name_to_user("bob") is None
    bot.kb = {}
    assert bot._discord_name_to_user("alice") is None


def test_homebot_on_ready_no_guild():
    server = FakeServer()
    server.knowledge = {}
    owner = type("O", (), {"knowledge": server.knowledge})()
    bot = HomeBot(owner)
    asyncio.run(bot.on_ready())  # no guild -> early return, no crash


def test_homebot_get_user_by_name():
    server = FakeServer()
    server.knowledge = {"DiscordUserMap": {"123": "alice"}}
    owner = type("O", (), {"knowledge": server.knowledge})()
    bot = HomeBot(owner)
    # no guild -> returns None without accessing members
    assert bot.get_user_by_name("alice") is None
    # no map
    bot.kb = {}
    assert bot.get_user_by_name("alice") is None
    # no match
    bot.kb = {"DiscordUserMap": {"123": "alice"}}
    assert bot.get_user_by_name("bob") is None


def test_homebot_send_message_to_user():
    server = FakeServer()
    server.knowledge = {}
    owner = type("O", (), {"knowledge": server.knowledge})()
    bot = HomeBot(owner)

    # user.send returns a coroutine -> scheduled on the loop (never runs) -> True
    async def send(self, msg):
        return None

    user = type("U", (), {"send": send})()
    assert bot.send_message_to_user(user, "hi") is True


def test_discord_messenger_stop_when_not_running():
    server = FakeServer()
    server.knowledge = {"DiscordToken": "t"}
    owner = type("O", (), {"knowledge": server.knowledge})()
    dm = DiscordMessenger(owner)
    dm.init()
    dm.stop()  # not running -> no-op
    assert dm.is_running is False
    dm.fini()
