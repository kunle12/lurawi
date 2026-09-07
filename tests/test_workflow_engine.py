"""Tests for the WorkflowEngine, RemoteService and webhook/workflow service."""

import asyncio
import json

import pytest

from lurawi.remote_service import RemoteService
from lurawi.webhook_handler import WebhookHandler
from lurawi.workflow_engine import WorkflowEngine, WorkflowInputPayload
from lurawi.workflow_service import WorkflowService

# ---------------- WorkflowEngine ----------------


def test_engine_init_and_knowledge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "default_knowledge.json").write_text(json.dumps({"PROJECT_NAME": "p"}))
    (tmp_path / "test_beh.json").write_text(
        json.dumps({"default": "__init__", "behaviours": [{"name": "__init__", "actions": []}]})
    )
    engine = WorkflowEngine("test_beh")
    assert engine.knowledge.get("PROJECT_NAME") == "p"
    assert engine.behaviours["default"] == "__init__"
    engine.on_shutdown()


def test_load_knowledge_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = WorkflowEngine("missing")
    assert engine.load_knowledge("nope") is True  # not found is not an error


def test_load_behaviours_missing_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.json").write_text(json.dumps({"behaviours": []}))
    engine = WorkflowEngine("missing")
    assert engine.load_behaviours("bad") == {"behaviours": []}
    assert engine.load_behaviours("bad.json") == {}  # warns about extension
    assert engine.load_behaviours("") == {}  # no behaviour


def test_load_pending_behaviours_no_members(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pb.json").write_text(
        json.dumps({"default": "__init__", "behaviours": [{"name": "__init__", "actions": []}]})
    )
    engine = WorkflowEngine("missing")
    msg = engine.load_pending_behaviours("pb")
    assert "reloaded" in msg
    assert engine.behaviours["default"] == "__init__"
    # corrupted -> ignore (empty dict loads to a falsy value)
    (tmp_path / "corrupt.json").write_text(json.dumps({}))
    assert "corrupted" in engine.load_pending_behaviours("corrupt")


def test_on_event_unauthorized():
    engine = WorkflowEngine("missing")
    resp = asyncio.run(engine.on_event(WorkflowInputPayload(uid="u", name="n"), authorised=False))
    assert resp.status_code == 401


def test_on_event_new_member_and_continue():
    engine = WorkflowEngine("missing")
    payload = WorkflowInputPayload(uid="u1", name="n", session_id="s", data={"message": "hi"})
    asyncio.run(engine.on_event(payload, authorised=True))
    assert "u1" in engine.conversation_members
    # continue with an existing member
    payload2 = WorkflowInputPayload(uid="u1", name="n", activity_id="a", data={"message": "again"})
    asyncio.run(engine.on_event(payload2, authorised=True))
    engine.on_shutdown()


def test_on_code_update():
    engine = WorkflowEngine("missing")
    from lurawi.workflow_engine import BehaviourCodePayload

    # invalid json
    resp = asyncio.run(engine.on_code_update(BehaviourCodePayload(jsonCode="not json")))
    assert resp.status_code == 400
    # missing default
    resp = asyncio.run(
        engine.on_code_update(BehaviourCodePayload(jsonCode=json.dumps({"behaviours": []})))
    )
    assert resp.status_code == 400
    # valid
    code = json.dumps({"default": "__init__", "behaviours": [{"name": "__init__", "actions": []}]})
    resp = asyncio.run(engine.on_code_update(BehaviourCodePayload(jsonCode=code)))
    assert resp.status_code == 200
    assert engine.behaviours["default"] == "__init__"


@pytest.mark.asyncio
async def test_get_member_and_execute():
    engine = WorkflowEngine("missing")
    assert engine.get_member("none") is None
    await engine.on_event(WorkflowInputPayload(uid="u2", name="n", data={}), authorised=True)
    assert engine.get_member("u2") is not None
    await engine.on_executing_behaviour_for_uid("u2", "main")
    assert await engine.on_executing_behaviour_for_uid("nope", "main") is False


def test_health_check():
    engine = WorkflowEngine("missing")
    resp = asyncio.run(engine.health_check())
    assert resp.status_code == 200
    assert resp.body is not None


def test_pending_load_complete():
    engine = WorkflowEngine("missing")
    engine.pending_behaviours = {"default": "x", "behaviours": []}
    engine.pending_behaviours_load_cnt = 1
    asyncio.run(engine.on_pending_load_complete())
    assert engine.behaviours == {"default": "x", "behaviours": []}
    assert engine.pending_behaviours == {}
    # no-op when count already 0
    engine.pending_behaviours_load_cnt = 0
    asyncio.run(engine.on_pending_load_complete())


def test_on_timer_and_purge_idle_users():
    engine = WorkflowEngine("missing")
    # register a member with a very old access time
    payload = WorkflowInputPayload(uid="idle", name="n", data={})
    asyncio.run(engine.on_event(payload, authorised=True))
    member = engine.get_member("idle")
    member.access_time = 0  # idle for a long time
    engine.auto_purge_timer = 123
    asyncio.run(engine.on_timer(123))
    assert engine.get_member("idle") is None


def test_remote_services_init_and_shutdown():
    engine = WorkflowEngine("missing")
    # discord service is skipped without a token
    engine._init_remote_services()
    engine.start_remote_services()
    engine.stop_remote_services()
    engine.on_shutdown()


# ---------------- RemoteService ----------------


class FakeOwner:
    def __init__(self):
        self.knowledge = {"MODULES": {}}


def test_remote_service_lifecycle():
    svc = RemoteService(FakeOwner())
    assert svc.is_initialised is False
    assert svc.is_running is False
    assert svc.init() is False
    svc._is_initialised = True
    svc.start()
    assert svc.is_running is True
    svc.stop()
    assert svc.is_running is False


def test_remote_service_timers():
    svc = RemoteService(FakeOwner())
    svc._is_initialised = True
    # invalid interval
    assert svc.register_for_timer(-1) is None
    tid = svc.register_for_timer(1)
    assert tid in svc._timers
    svc.cancel_timer(tid)
    assert tid not in svc._timers
    svc.cancel_timer(99999)  # no-op
    tid2 = svc.register_for_timer(1)
    asyncio.run(svc.on_timer_lapsed(tid2))
    assert tid2 not in svc._timers
    svc.register_for_timer(1)
    svc.cancel_timers()
    assert svc._timers == []
    svc.fini()
    assert svc.is_initialised is False


# ---------------- WebhookHandler ----------------


def test_webhook_handler_defaults():
    h = WebhookHandler()
    assert h.route == "/unknown"
    assert h.methods == ["POST"]
    assert h.is_disabled is False
    resp = asyncio.run(h.process_callback(None))
    assert resp.status_code == 200
    h.write_http_response(200, {"status": "ok"})
    h.fini()  # no-op


# ---------------- WorkflowService ----------------


def test_workflow_service_create_app(monkeypatch):
    monkeypatch.setenv("BackendOperationEnabled", "1")
    monkeypatch.setenv("RemoteWebhookURL", "http://localhost:8081")
    monkeypatch.setattr("lurawi.utils.in_dev", True)
    svc = WorkflowService("missing")
    app = svc.create_app()
    assert app is not None
    assert svc.app is app
    # handlers were discovered from lurawi/handlers
    assert svc.webhook_handlers


def test_workflow_service_lifespan():
    svc = WorkflowService("missing")
    app = svc.create_app()

    async def run():
        async with svc.lifespan(app):
            pass

    asyncio.run(run())


def test_load_knowledge_azure(monkeypatch, tmp_path):
    import lurawi.workflow_engine as we

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AzureWebJobsStorage", "conn")

    class FakeBlob:
        def download_blob(self):
            class Resp:
                def content_as_text(self):
                    return json.dumps({"PROJECT_NAME": "p"})

            return Resp()

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setattr(we, "BlobClient", FakeBlobClient)
    engine = we.WorkflowEngine("missing")
    assert engine.load_knowledge("default_knowledge") is True
    assert engine.knowledge.get("PROJECT_NAME") == "p"


def test_load_behaviours_azure(monkeypatch, tmp_path):
    import lurawi.workflow_engine as we

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AzureWebJobsStorage", "conn")

    class FakeBlob:
        def download_blob(self):
            class Resp:
                def content_as_text(self):
                    return json.dumps({"default": "__init__", "behaviours": []})

            return Resp()

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setattr(we, "BlobClient", FakeBlobClient)
    engine = we.WorkflowEngine("missing")
    loaded = engine.load_behaviours("test_beh")
    assert loaded["default"] == "__init__"


def test_load_knowledge_aws(monkeypatch, tmp_path):
    import lurawi.workflow_engine as we

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UseAWSS3", "1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")

    class FakeS3:
        def download_fileobj(self, bucket, key, io):
            io.write(json.dumps({"PROJECT_NAME": "p"}))

    monkeypatch.setattr(we.boto3, "client", lambda svc: FakeS3())
    engine = we.WorkflowEngine("missing")
    assert engine.load_knowledge("default_knowledge") is True
    assert engine.knowledge.get("PROJECT_NAME") == "p"


def test_on_discord_event(monkeypatch):
    engine = WorkflowEngine("missing")
    message = type("Msg", (), {})()
    message.author = type("A", (), {"id": 123})()
    message.content = "hello"
    message.attachments = []
    asyncio.run(engine.on_discord_event("alice", message))
    assert "123" in engine.conversation_members
    # existing member continues
    asyncio.run(engine.on_discord_event("alice", message))
    # with an image attachment
    msg2 = type("Msg", (), {})()
    msg2.author = type("A", (), {"id": 456})()
    msg2.content = "pic"
    msg2.attachments = [type("At", (), {"content_type": "image/png", "url": "http://x/img.png"})()]
    asyncio.run(engine.on_discord_event("bob", msg2))
    assert "456" in engine.conversation_members
    engine.on_shutdown()
