"""Parametrized tests for the custom behaviour modules."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from lurawi.callbackmsg_manager import RemoteCallbackMessageUpdateManager
from lurawi.usermsg_manager import UserMessageUpdateManager


async def _noop_message(*a, **kw):
    return None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps({"posted": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        self.do_POST()

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def make_kb(extra=None):
    kb = {
        "MODULES": {},
        "USER_INPUTS_CACHE": [],
        "LURAWI_SYSTEM_SERVICES": {},
        "MESG_FUNC": _noop_message,
    }
    from threading import Lock

    kb["__MUTEX__"] = Lock()
    kb["MODULES"]["UserMessageManager"] = UserMessageUpdateManager(kb)
    kb["MODULES"]["RemoteCallbackMessageManager"] = RemoteCallbackMessageUpdateManager(kb)
    if extra:
        kb.update(extra)
    return kb


async def run_custom(cls, kb, details):
    obj = cls(kb, details)
    result = {"succeeded": False, "failed": False}

    async def ok(*a):
        result["succeeded"] = True

    async def fail(*a):
        result["failed"] = True

    obj.on_success = ok
    obj.on_failure = fail
    await obj.run()
    return result, obj


# ---- current_datetime ----
@pytest.mark.asyncio
async def test_current_datetime_success():
    r, obj = await run_custom(
        __import__("lurawi.custom.current_datetime", fromlist=["*"]).current_datetime,
        make_kb(),
        {"output": "NOW"},
    )
    assert r["succeeded"] is True
    assert "NOW" in obj.kb
    # default output key
    r2, obj2 = await run_custom(
        __import__("lurawi.custom.current_datetime", fromlist=["*"]).current_datetime, make_kb(), {}
    )
    assert obj2.kb["CURRENT_DATETIME"]


# ---- random_picker ----
@pytest.mark.asyncio
async def test_random_picker():
    from lurawi.custom.random_picker import random_picker

    r, obj = await run_custom(random_picker, make_kb(), {"list": ["a", "b"], "output": "PICK"})
    assert r["succeeded"] is True
    assert obj.kb["PICK"] in ("a", "b")
    # empty list -> failed
    r2, _ = await run_custom(random_picker, make_kb(), {"list": [], "output": "P"})
    assert r2["failed"] is True
    # missing output -> failed
    r3, _ = await run_custom(random_picker, make_kb(), {"list": ["a"]})
    assert r3["failed"] is True


# ---- get_keyvalue ----
@pytest.mark.asyncio
async def test_get_keyvalue():
    from lurawi.custom.get_keyvalue import get_keyvalue

    kb = make_kb({"STORE": {"team": "red"}, "KEY": "team"})
    r, obj = await run_custom(get_keyvalue, kb, {"store": "STORE", "key": "KEY", "value": "OUT"})
    assert r["succeeded"] is True
    assert obj.kb["OUT"] == "red"
    # default output key
    r2, obj2 = await run_custom(
        get_keyvalue, make_kb({"STORE": {"a": 1}}), {"store": "STORE", "key": "a"}
    )
    assert obj2.kb["_VALUE_OUTPUT"] == 1
    # missing key -> failed
    r3, _ = await run_custom(
        get_keyvalue, make_kb({"STORE": {}}), {"store": "STORE", "key": "nope"}
    )
    assert r3["failed"] is True
    # store not dict -> failed
    r4, _ = await run_custom(
        get_keyvalue, make_kb({"STORE": "notdict"}), {"store": "STORE", "key": "a"}
    )
    assert r4["failed"] is True
    # missing details -> failed
    r5, _ = await run_custom(get_keyvalue, make_kb(), {})
    assert r5["failed"] is True


# ---- get_indexvalue ----
@pytest.mark.asyncio
async def test_get_indexvalue():
    from lurawi.custom.get_indexvalue import get_indexvalue

    kb = make_kb({"ARR": [10, 20, 30], "IDX": 1})
    r, obj = await run_custom(get_indexvalue, kb, {"array": "ARR", "index": "IDX", "value": "OUT"})
    assert r["succeeded"] is True
    assert obj.kb["OUT"] == 20
    # out of bounds -> failed
    r2, _ = await run_custom(get_indexvalue, make_kb({"ARR": [1]}), {"array": "ARR", "index": 5})
    assert r2["failed"] is True
    # non-list array -> failed
    r3, _ = await run_custom(get_indexvalue, make_kb({"ARR": "x"}), {"array": "ARR", "index": 0})
    assert r3["failed"] is True
    # negative index -> failed
    r4, _ = await run_custom(get_indexvalue, make_kb({"ARR": [1]}), {"array": "ARR", "index": -1})
    assert r4["failed"] is True
    # missing details -> failed
    r5, _ = await run_custom(get_indexvalue, make_kb(), {})
    assert r5["failed"] is True


# ---- has_keyvalue ----
@pytest.mark.asyncio
async def test_has_keyvalue():
    from lurawi.custom.has_keyvalue import has_keyvalue

    kb = make_kb({"STORE": {"team": "red"}, "KEY": "team"})
    r, _ = await run_custom(
        has_keyvalue,
        kb,
        {
            "store": "STORE",
            "key": "KEY",
            "true_action": ["text", "t"],
            "false_action": ["text", "f"],
        },
    )
    assert r["succeeded"] is True
    r2, obj2 = await run_custom(
        has_keyvalue,
        make_kb({"STORE": {}}),
        {
            "store": "STORE",
            "key": "missing",
            "true_action": ["text", "t"],
            "false_action": ["text", "f"],
        },
    )
    assert r2["succeeded"] is True
    # store not found -> failed
    r3, _ = await run_custom(
        has_keyvalue,
        make_kb(),
        {"store": "NOPE", "key": "k", "true_action": ["text", "t"], "false_action": ["text", "f"]},
    )
    assert r3["failed"] is True
    # non-dict store -> fallback to kb
    r4, _ = await run_custom(
        has_keyvalue,
        make_kb({"X": 1}),
        {"key": "X", "true_action": ["text", "t"], "false_action": ["text", "f"]},
    )
    assert r4["succeeded"] is True
    # missing details -> failed
    r5, _ = await run_custom(has_keyvalue, make_kb(), {})
    assert r5["failed"] is True


# ---- query_knowledgebase ----
@pytest.mark.asyncio
async def test_query_knowledgebase():
    from lurawi.custom.query_knowledgebase import query_knowledgebase

    kb = make_kb({"DATA": json.dumps({"a": 1}), "Q": "a"})
    r, obj = await run_custom(
        query_knowledgebase, kb, {"knowledge_key": "DATA", "query_arg": "Q", "query_output": "OUT"}
    )
    assert r["succeeded"] is True
    assert obj.kb["OUT"] == 1
    # phrase match
    kb2 = make_kb({"PEOPLE": {"bob": {"phrases": ["bob", "robert"]}}, "NAME": "bob"})
    r2, obj2 = await run_custom(
        query_knowledgebase,
        kb2,
        {
            "knowledge_key": "PEOPLE",
            "query_arg": "NAME",
            "phrase_match": True,
            "phrase_match_key": "PM",
        },
    )
    assert r2["succeeded"] is True
    assert obj2.kb["PM"] == "bob"
    # no query_arg -> whole value
    r3, _ = await run_custom(
        query_knowledgebase, make_kb({"DATA": {"a": 1}}), {"knowledge_key": "DATA"}
    )
    assert r3["succeeded"] is True
    # missing knowledge_key -> failed
    r4, _ = await run_custom(query_knowledgebase, make_kb(), {})
    assert r4["failed"] is True
    # key not in kb -> failed
    r5, _ = await run_custom(query_knowledgebase, make_kb(), {"knowledge_key": "NOPE"})
    assert r5["failed"] is True
    # query_arg dict without query_key -> failed
    r6, _ = await run_custom(
        query_knowledgebase,
        make_kb({"DATA": {"a": 1}}),
        {"knowledge_key": "DATA", "query_arg": {"other": 1}, "query_key": "a"},
    )
    assert r6["failed"] is True
    # string kb value that's not JSON -> failed
    r7, _ = await run_custom(
        query_knowledgebase,
        make_kb({"DATA": "notjson"}),
        {"knowledge_key": "DATA", "query_arg": "Q"},
    )
    assert r7["failed"] is True
    # no match -> failed
    r8, _ = await run_custom(
        query_knowledgebase,
        make_kb({"DATA": {"a": 1}}),
        {"knowledge_key": "DATA", "query_arg": "zzz"},
    )
    assert r8["failed"] is True


# ---- build_gpt_prompt ----
@pytest.mark.asyncio
async def test_build_gpt_prompt():
    from lurawi.custom.build_gpt_prompt import build_gpt_prompt

    kb = make_kb({"USER": "hello", "SYS": "you are {}"})
    r, obj = await run_custom(
        build_gpt_prompt, kb, {"system_prompt": "SYS", "user_prompt": "USER", "output": "PROMPT"}
    )
    assert r["succeeded"] is True
    assert any(m.get("role") == "user" and m.get("content") == "hello" for m in obj.kb["PROMPT"])
    # oversized prompt with no docs/history -> failed
    r2, _ = await run_custom(
        build_gpt_prompt, make_kb(), {"user_prompt": "x" * 3000, "output": "P", "max_tokens": 1}
    )
    assert r2["failed"] is True


# ---- validate_with_regex ----
@pytest.mark.asyncio
async def test_validate_with_regex():
    from lurawi.custom.validate_with_regex import validate_with_regex

    kb = make_kb({"TEXT": "abc123"})
    r, _ = await run_custom(validate_with_regex, kb, {"input_text": "TEXT", "regex": "^[a-z0-9]+$"})
    assert r["succeeded"] is True
    # no match -> failed
    r2, _ = await run_custom(
        validate_with_regex, make_kb({"TEXT": "abc"}), {"input_text": "TEXT", "regex": "^[0-9]+$"}
    )
    assert r2["failed"] is True
    # invalid regex -> failed
    r3, _ = await run_custom(
        validate_with_regex, make_kb({"TEXT": "a"}), {"input_text": "TEXT", "regex": "("}
    )
    assert r3["failed"] is True
    # missing input_text -> failed
    r4, _ = await run_custom(validate_with_regex, make_kb(), {"regex": "^a+$"})
    assert r4["failed"] is True


# ---- text_input ----
@pytest.mark.asyncio
async def test_text_input():
    from lurawi.custom.text_input import text_input

    kb = make_kb({"GUEST": "bob"})
    obj = text_input(kb, {"prompt": ["hi {}", ["GUEST"]], "output": "RESP"})

    async def ok(*a):
        obj._succeeded = True

    obj.on_success = ok
    await obj.run()
    assert obj.data_key == "RESP"
    # user message update stores the response
    await obj.on_user_message_update({"message": "hello there"})
    assert kb["RESP"] == "hello there"
    # missing output -> failed
    obj2 = text_input(kb, {})
    failed = []

    async def fail(*a):
        failed.append(True)

    obj2.on_failure = fail
    await obj2.run()
    assert failed == [True]
    # invalid prompt type -> prompt empty
    obj3 = text_input(kb, {"prompt": 123, "output": "R"})
    await obj3.run()
    # non-dict message context -> failed
    obj4 = text_input(kb, {"output": "R"})
    failed2 = []

    async def fail2(*a):
        failed2.append(True)

    obj4.on_failure = fail2
    await obj4.run()
    await obj4.on_user_message_update("notadict")
    assert failed2 == [True]


# ---- populate_prompt ----
@pytest.mark.asyncio
async def test_populate_prompt():
    from lurawi.custom.populate_prompt import populate_prompt

    kb = make_kb({"NAME": "bob"})
    r, obj = await run_custom(
        populate_prompt,
        kb,
        {"prompt_text": "hi {NAME}", "replace": {"{NAME}": "NAME"}, "output": "OUT"},
    )
    assert r["succeeded"] is True
    assert obj.kb["OUT"] == "hi bob"
    # invalid -> failed
    r2, _ = await run_custom(populate_prompt, make_kb(), {"prompt_text": "x", "replace": "notdict"})
    assert r2["failed"] is True
    r3, _ = await run_custom(populate_prompt, make_kb(), {"replace": {"a": "b"}})
    assert r3["failed"] is True


# ---- cache_conversation_history ----
@pytest.mark.asyncio
async def test_cache_conversation_history():
    from lurawi.custom.cache_conversation_history import cache_conversation_history

    kb = make_kb({"USER": "hi", "LLM": "hello"})
    r, obj = await run_custom(
        cache_conversation_history,
        kb,
        {"user_input": "USER", "llm_output": "LLM", "history": "HIST"},
    )
    assert r["succeeded"] is True
    assert "HIST" in obj.kb
    # missing args default to empty and still succeed
    r2, _ = await run_custom(
        cache_conversation_history, make_kb(), {"user_input": "U", "llm_output": "L"}
    )
    assert r2["succeeded"] is True


# ---- behaviour_router ----
@pytest.mark.asyncio
async def test_behaviour_router():
    from lurawi.custom.behaviour_router import behaviour_router

    kb = make_kb({"KEY": "v"})
    # provide an ActivityManager with behaviours for the __init__ access
    fake_am = type("AM", (), {})()
    fake_am.behaviours = {
        "behaviours": [{"name": "x", "actions": []}, {"name": "y", "actions": []}]
    }
    kb["MODULES"]["ActivityManager"] = fake_am
    r, _ = await run_custom(
        behaviour_router,
        kb,
        {"select": "x", "true_action": ["text", "t"], "false_action": ["text", "f"]},
    )
    assert r["succeeded"] is True
    r2, _ = await run_custom(
        behaviour_router,
        kb,
        {"select": "missing", "true_action": ["text", "t"], "false_action": ["text", "f"]},
    )
    assert r2["failed"] is True
    # restricted without behaviours -> failed
    r3, _ = await run_custom(
        behaviour_router,
        kb,
        {
            "select": "x",
            "restricted": True,
            "true_action": ["text", "t"],
            "false_action": ["text", "f"],
        },
    )
    assert r3["failed"] is True
    # random selection
    r4, _ = await run_custom(
        behaviour_router,
        kb,
        {"select": "random", "true_action": ["text", "t"], "false_action": ["text", "f"]},
    )
    assert r4["succeeded"] is True
    # missing select -> failed
    r5, _ = await run_custom(
        behaviour_router, kb, {"true_action": ["text", "t"], "false_action": ["text", "f"]}
    )
    assert r5["failed"] is True


# ---- web_search (missing creds -> failed) ----
@pytest.mark.asyncio
async def test_web_search_missing_creds():
    from lurawi.custom.web_search import web_search

    r, _ = await run_custom(web_search, make_kb(), {"search_terms": "hello"})
    assert r["failed"] is True
    r2, _ = await run_custom(web_search, make_kb(), {})
    assert r2["failed"] is True


# ---- invoke_llm (missing config -> failed) ----
@pytest.mark.asyncio
async def test_invoke_llm_missing_config():
    from lurawi.custom.invoke_llm import invoke_llm

    r, _ = await run_custom(invoke_llm, make_kb(), {"base_url": "x", "api_key": "y", "model": "m"})
    assert r["failed"] is True  # missing prompt
    r2, _ = await run_custom(invoke_llm, make_kb(), {"base_url": "x", "model": "m", "prompt": "hi"})
    assert r2["failed"] is True  # missing api_key


# ---- get_data_from_url (network error -> failed) ----
@pytest.mark.asyncio
async def test_get_data_from_url_error():
    from lurawi.custom.get_data_from_url import get_data_from_url

    r, _ = await run_custom(
        get_data_from_url, make_kb(), {"url": "http://127.0.0.1:1/x", "output": "O"}
    )
    assert r["failed"] is True


# ---- send_data_to_url (network error -> failed) ----
@pytest.mark.asyncio
async def test_send_data_to_url_error():
    from lurawi.custom.send_data_to_url import send_data_to_url

    r, _ = await run_custom(
        send_data_to_url, make_kb(), {"url": "http://127.0.0.1:1/x", "payload": {"a": 1}}
    )
    assert r["failed"] is True


# ---- file_loader (missing file -> failed) ----
@pytest.mark.asyncio
async def test_file_loader_error(tmp_path):
    from lurawi.custom.file_loader import file_loader

    r, _ = await run_custom(
        file_loader, make_kb(), {"file_location": str(tmp_path / "nope.txt"), "file_type": "txt"}
    )
    assert r["failed"] is True


# ---- discord_message ----
@pytest.mark.asyncio
async def test_discord_message():
    from lurawi.custom.discord_message import discord_message

    r, _ = await run_custom(discord_message, make_kb(), {"message": "hello", "user": "u"})
    assert r["failed"] is True  # no discord service configured


# ---- user_file_upload (missing file -> failed) ----
@pytest.mark.asyncio
async def test_user_file_upload_error(tmp_path):
    from lurawi.custom.user_file_upload import user_file_upload

    r, _ = await run_custom(
        user_file_upload, make_kb(), {"file_location": str(tmp_path / "nope.png")}
    )
    assert r["failed"] is True


# ---- chromadb_search (missing config -> failed) ----
@pytest.mark.asyncio
async def test_chromadb_search_missing():
    from lurawi.custom.chromadb_search import chromadb_search

    r, _ = await run_custom(chromadb_search, make_kb(), {"search_text": "q"})
    assert r["failed"] is True


# ---- file_loader ----
@pytest.mark.asyncio
async def test_file_loader_text_success(tmp_path):
    from lurawi.custom.file_loader import file_loader

    p = tmp_path / "notes.txt"
    p.write_text("hello world")
    r, obj = await run_custom(
        file_loader, make_kb(), {"file_type": "text", "file_location": str(p), "output": "OUT"}
    )
    assert r["succeeded"] is True
    assert obj.kb["OUT"] == [{"type": "text", "text": "hello world"}]


@pytest.mark.asyncio
async def test_file_loader_failures():
    from lurawi.custom.file_loader import file_loader

    # invalid file type
    r, _ = await run_custom(file_loader, make_kb(), {"file_type": "exe", "file_location": "/tmp/x"})
    assert r["failed"] is True
    # invalid path
    r2, _ = await run_custom(
        file_loader, make_kb(), {"file_type": "text", "file_location": "/no/such/file"}
    )
    assert r2["failed"] is True


# ---- chromadb_search (validation failures) ----
@pytest.mark.asyncio
async def test_chromadb_search_validation_failures(tmp_path):
    from lurawi.custom.chromadb_search import chromadb_search

    # missing collection
    r, _ = await run_custom(
        chromadb_search, make_kb(), {"search_text": "q", "directory": str(tmp_path)}
    )
    assert r["failed"] is True
    # missing search_text
    r2, _ = await run_custom(
        chromadb_search, make_kb(), {"collection": "c", "directory": str(tmp_path)}
    )
    assert r2["failed"] is True
    # missing directory
    r3, _ = await run_custom(chromadb_search, make_kb(), {"collection": "c", "search_text": "q"})
    assert r3["failed"] is True
    # non-existent directory
    r4, _ = await run_custom(
        chromadb_search,
        make_kb(),
        {"collection": "c", "search_text": "q", "directory": str(tmp_path / "nope")},
    )
    assert r4["failed"] is True


@pytest.mark.asyncio
async def test_chromadb_search_embedding_model(tmp_path, monkeypatch):
    import lurawi.custom.chromadb_search as cmod

    d = tmp_path / "db"
    d.mkdir()
    kb = make_kb({"LURAWI_WORKSPACE": str(tmp_path)})

    # mock PersistentClient to avoid heavy real chroma init
    class FakeClient:
        def get_collection(self, **kw):
            raise Exception("no collection")

    monkeypatch.setattr(cmod, "PersistentClient", lambda path, settings: FakeClient())
    # gguf model file missing -> failed
    r, _ = await run_custom(
        cmod.chromadb_search,
        kb,
        {"collection": "c", "search_text": "q", "directory": str(d), "embedding_model": "m.gguf"},
    )
    assert r["failed"] is True
    # non-gguf model -> fails at collection load (provide api creds to avoid ValueError)
    r2, _ = await run_custom(
        cmod.chromadb_search,
        kb,
        {
            "collection": "c",
            "search_text": "q",
            "directory": str(d),
            "embedding_model": "openai-model",
            "api_key": "k",
            "base_url": "http://x",
        },
    )
    assert r2["failed"] is True


# ---- send_data_to_url ----
@pytest.mark.asyncio
async def test_send_data_to_url_success(http_server):
    from lurawi.custom.send_data_to_url import send_data_to_url

    r, obj = await run_custom(
        send_data_to_url,
        make_kb(),
        {"url": f"{http_server}/post", "payload": {"a": 1}, "return_data": "RESP"},
    )
    assert r["succeeded"] is True
    assert obj.kb["RESP"] == {"posted": True}


@pytest.mark.asyncio
async def test_send_data_to_url_failures():
    from lurawi.custom.send_data_to_url import send_data_to_url

    # missing url
    r, _ = await run_custom(send_data_to_url, make_kb(), {"payload": {"a": 1}})
    assert r["failed"] is True
    # missing payload
    r2, _ = await run_custom(send_data_to_url, make_kb(), {"url": "http://x"})
    assert r2["failed"] is True
    # network error
    r3, _ = await run_custom(
        send_data_to_url, make_kb(), {"url": "http://127.0.0.1:1/x", "payload": {"a": 1}}
    )
    assert r3["failed"] is True


# ---- get_data_from_url ----
@pytest.mark.asyncio
async def test_get_data_from_url_success(http_server):
    from lurawi.custom.get_data_from_url import get_data_from_url

    r, obj = await run_custom(
        get_data_from_url, make_kb(), {"url": f"{http_server}/get", "return_data": "DATA"}
    )
    assert r["succeeded"] is True
    assert obj.kb["DATA"] == {"ok": True}


# ---- invoke_llm (mocked OpenAI) ----
@pytest.mark.asyncio
async def test_invoke_llm_success(monkeypatch):
    from lurawi.custom import invoke_llm as m

    class FakeCompletions:
        async def create(self, **kw):
            choice = type("Ch", (), {"message": type("Msg", (), {"content": "answer"})()})()
            return type("Resp", (), {"choices": [choice]})()

    fake = type("Client", (), {"chat": type("C", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(m, "AsyncOpenAI", lambda **kw: fake)

    r, obj = await run_custom(
        m.invoke_llm,
        make_kb(),
        {"base_url": "http://x", "api_key": "k", "model": "m", "prompt": "hi"},
    )
    assert r["succeeded"] is True
    assert obj.kb["LLM_RESPONSE"] == "answer"


@pytest.mark.asyncio
async def test_invoke_llm_stream(monkeypatch):
    from lurawi.custom import invoke_llm as m

    class FakeStream:
        async def __aiter__(self):
            yield type(
                "Ch",
                (),
                {"choices": [type("C", (), {"delta": type("D", (), {"content": "hi"})()})()]},
            )()

    class FakeCompletions:
        async def create(self, **kw):
            return FakeStream()

    fake = type("Client", (), {"chat": type("C", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(m, "AsyncOpenAI", lambda **kw: fake)

    r, obj = await run_custom(
        m.invoke_llm,
        make_kb(),
        {
            "base_url": "http://x",
            "api_key": "k",
            "model": "m",
            "prompt": "hi",
            "stream": True,
            "response": "OUT",
        },
    )
    # streaming path does not call succeeded() until the stream is consumed
    assert r["failed"] is False


@pytest.mark.asyncio
async def test_invoke_llm_prompt_resolution(monkeypatch):
    from lurawi.custom import invoke_llm as m

    class FailingCompletions:
        async def create(self, **kw):
            raise RuntimeError("no server")

    fake = type("Client", (), {"chat": type("C", (), {"completions": FailingCompletions()})()})()
    monkeypatch.setattr(m, "AsyncOpenAI", lambda **kw: fake)

    kb = make_kb({"NAME": "bob", "MSG": "hi {}"})
    # template prompt list
    r, _ = await run_custom(
        m.invoke_llm,
        kb,
        {"base_url": "x", "api_key": "y", "model": "m", "prompt": ["hi {}", ["NAME"]]},
    )
    assert r["failed"] is True  # API call fails
    # dict messages prompt with nested template
    r2, _ = await run_custom(
        m.invoke_llm,
        kb,
        {
            "base_url": "x",
            "api_key": "y",
            "model": "m",
            "prompt": [{"role": "user", "content": ["hi {}", ["NAME"]]}],
        },
    )
    assert r2["failed"] is True


# ---- web_search (helpers + simple mode, mocked search) ----
@pytest.mark.asyncio
async def test_web_search_helpers():
    from lurawi.custom.web_search import web_search

    assert web_search._strip_html("<p>hello <b>world</b></p>") == "hello world"
    obj = web_search(make_kb(), {})
    qs = obj._generate_sub_queries("compare A and B and C")
    assert len(qs) == 3
    qs2 = obj._generate_sub_queries("short question")
    assert len(qs2) == 3


@pytest.mark.asyncio
async def test_web_search_simple_mode_mocked(monkeypatch):
    from lurawi.custom.web_search import web_search

    async def fake_search(self, q, base, n):
        return [{"title": "t", "url": "http://x", "snippet": "s", "content": ""}]

    async def fake_fetch(self, url):
        return "page content"

    monkeypatch.setattr(web_search, "_searxng_search", fake_search)
    monkeypatch.setattr(web_search, "_fetch_page_content", fake_fetch)
    r, obj = await run_custom(
        web_search, make_kb(), {"search_terms": "q", "searxng_url": "http://x"}
    )
    assert r["succeeded"] is True
    assert obj.kb["WEB_SEARCH_RESULTS"]["total_sources"] == 1


# ---- user_file_upload (validation) ----
@pytest.mark.asyncio
async def test_user_file_upload_validation():
    from lurawi.custom.user_file_upload import user_file_upload

    # missing type
    r, _ = await run_custom(user_file_upload, make_kb(), {"output": "O"})
    assert r["failed"] is True
    # unsupported type
    r2, _ = await run_custom(user_file_upload, make_kb(), {"type": "exe", "output": "O"})
    assert r2["failed"] is True
    # non-string type
    r3, _ = await run_custom(user_file_upload, make_kb(), {"type": 123, "output": "O"})
    assert r3["failed"] is True
    # missing output
    r4, _ = await run_custom(user_file_upload, make_kb(), {"type": "json|txt"})
    assert r4["failed"] is True


@pytest.mark.asyncio
async def test_user_file_upload_run_with_prompt():
    from lurawi.custom.user_file_upload import user_file_upload

    kb = make_kb({"GUEST": "bob"})
    obj = user_file_upload(kb, {"type": "txt", "output": "FILE", "prompt": ["hi {}", ["GUEST"]]})

    async def ok(*a):
        obj._ok = True

    obj.on_success = ok
    await obj.run()
    assert obj.data_key == "FILE"
    assert obj.content_types == ["txt"]


# ---- web_search network paths ----
@pytest.mark.asyncio
async def test_web_search_fetch_page_content(http_server):
    from lurawi.custom.web_search import web_search

    obj = web_search(make_kb(), {})
    text = await obj._fetch_page_content(f"{http_server}/page")
    assert "hello world" in text or text is not None
    assert await obj._fetch_page_content("http://127.0.0.1:1/nope") is None


@pytest.mark.asyncio
async def test_web_search_backends_error(monkeypatch):
    from lurawi.custom import web_search as m

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            raise RuntimeError("no net")

        async def get(self, url):
            raise RuntimeError("no net")

    monkeypatch.setattr(m.aiohttp, "ClientSession", lambda **kw: FakeSession())
    obj = m.web_search(make_kb(), {})
    assert await obj._firecrawl_search("q", "bad-key", 5) == []
    assert await obj._searxng_search("q", "http://x", 5) == []


@pytest.mark.asyncio
async def test_web_search_deep_research_mocked(monkeypatch):
    from lurawi.custom.web_search import web_search

    async def fake_search(self, q, base, n):
        return [{"title": "t", "url": "http://x", "snippet": "s", "content": ""}]

    async def fake_fetch(self, url):
        return "page content"

    monkeypatch.setattr(web_search, "_searxng_search", fake_search)
    monkeypatch.setattr(web_search, "_fetch_page_content", fake_fetch)
    obj = web_search(make_kb(), {})
    result = await obj._deep_research("compare A vs B", 5, 2, "searxng", searxng_url="http://x")
    assert result["total_sources"] == 1
    assert result["summary"] == ""


@pytest.mark.asyncio
async def test_web_search_llm_synthesis_error(monkeypatch):
    import openai

    from lurawi.custom import web_search as m

    class FailingCompletions:
        async def create(self, **kw):
            raise RuntimeError("no llm")

    fake = type("Client", (), {"chat": type("C", (), {"completions": FailingCompletions()})()})()
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kw: fake)
    obj = m.web_search(make_kb(), {})
    synthesis, gaps = await obj._call_llm_for_synthesis("ctx", "q", "http://x", "k", "m")
    assert synthesis == ""
    assert gaps == []


# ---- file_loader image ----
@pytest.mark.asyncio
async def test_file_loader_image_success(tmp_path):
    from PIL import Image

    from lurawi.custom.file_loader import file_loader

    p = tmp_path / "img.png"
    Image.new("RGB", (100, 100), (255, 0, 0)).save(p)
    r, obj = await run_custom(
        file_loader, make_kb(), {"file_type": "image", "file_location": str(p), "output": "IMG"}
    )
    assert r["succeeded"] is True
    assert obj.kb["IMG"][0]["type"] == "image_url"


# ---- chromadb_search query success (mocked) ----
@pytest.mark.asyncio
async def test_chromadb_search_query_success(tmp_path, monkeypatch):
    import lurawi.custom.chromadb_search as cmod

    d = tmp_path / "db"
    d.mkdir()
    kb = make_kb({"LURAWI_WORKSPACE": str(tmp_path)})

    class FakeStore:
        def query(self, query_texts, include):
            return {"documents": [["doc1", "doc2"]], "metadatas": [[{}]]}

    class FakeClient:
        def get_collection(self, name, embedding_function):
            return FakeStore()

    monkeypatch.setattr(cmod, "PersistentClient", lambda path, settings: FakeClient())
    r, obj = await run_custom(
        cmod.chromadb_search,
        kb,
        {
            "collection": "c",
            "search_text": "q",
            "directory": str(d),
            "embedding_model": "openai-model",
            "api_key": "k",
            "base_url": "http://x",
            "output": "OUT",
        },
    )
    assert r["succeeded"] is True
    assert "doc1" in obj.kb["OUT"]


# ---- user_file_upload on_user_message_update ----
@pytest.mark.asyncio
async def test_user_file_upload_on_update(monkeypatch):
    from lurawi.custom.user_file_upload import user_file_upload

    kb = make_kb({})
    obj = user_file_upload(kb, {"type": "txt", "output": "FILE"})

    async def ok(*a):
        obj._ok = True

    obj.on_success = ok
    # no attachments -> message prompt
    ctx = type("C", (), {})()
    ctx.activity = type("A", (), {"attachments": []})()
    await obj.on_user_message_update(ctx)
    assert getattr(obj, "_ok", None) is None

    # successful attachment handling
    async def handle(ctx):
        return True

    obj._handle_incoming_attachment = handle
    ctx2 = type("C", (), {})()
    ctx2.activity = type("A", (), {"attachments": [1]})()
    await obj.on_user_message_update(ctx2)
    assert obj._ok is True

    # failure
    async def handle_fail(ctx):
        return False

    obj._handle_incoming_attachment = handle_fail
    failed = []

    async def fail(*a):
        failed.append(True)

    obj.on_failure = fail
    ctx3 = type("C", (), {})()
    ctx3.activity = type("A", (), {"attachments": [1]})()
    await obj.on_user_message_update(ctx3)
    assert failed == [True]


@pytest.mark.asyncio
async def test_send_data_to_url_template_and_headers(http_server):
    from lurawi.custom.send_data_to_url import send_data_to_url

    kb = make_kb({"VALUE": "resolved", "HEADER_VAL": "hv"})
    r, obj = await run_custom(
        send_data_to_url,
        kb,
        {
            "url": f"{http_server}/post",
            "payload": {"a": "VALUE", "templ": ["x {}", ["VALUE"]]},
            "headers": {"X-H": "HEADER_VAL"},
            "return_status": "STATUS",
        },
    )
    assert r["succeeded"] is True
    assert obj.kb["STATUS"] == 200


@pytest.mark.asyncio
async def test_invoke_llm_nested_prompt_and_append(monkeypatch):
    from lurawi.custom import invoke_llm as m

    class FakeCompletions:
        async def create(self, **kw):
            choice = type("Ch", (), {"message": type("Msg", (), {"content": "answer"})()})()
            return type("Resp", (), {"choices": [choice]})()

    fake = type("Client", (), {"chat": type("C", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(m, "AsyncOpenAI", lambda **kw: fake)

    kb = make_kb({"NAME": "bob", "OUT": ["existing"]})
    r, obj = await run_custom(
        m.invoke_llm,
        kb,
        {
            "base_url": "http://x",
            "api_key": "k",
            "model": "m",
            "prompt": [{"role": "user", "content": ["hi {}", ["NAME"]]}],
            "response": "OUT",
        },
    )
    assert r["succeeded"] is True
    assert obj.kb["OUT"] == ["existing", "answer"]
