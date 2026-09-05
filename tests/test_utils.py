"""Tests for the utils module (helpers, storage, HTTP, crypto)."""

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import lurawi.utils as u

# ---------- local HTTP server helpers ----------


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

    def do_PATCH(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "5")
        self.end_headers()

    def log_message(self, *args):  # silence
        pass


@pytest.fixture(scope="module")
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join()


# ---------- basic ----------


def test_is_indev_and_project_settings(monkeypatch):
    u.in_dev = True
    assert u.is_indev() is True
    u.in_dev = False
    assert u.is_indev() is False
    monkeypatch.delenv("PROJECT_NAME", raising=False)
    monkeypatch.delenv("PROJECT_ACCESS_KEY", raising=False)
    assert u.get_project_settings() is False
    monkeypatch.setenv("PROJECT_NAME", "p")
    monkeypatch.setenv("PROJECT_ACCESS_KEY", "k")
    assert u.get_project_settings() is True
    assert u.project_name == "p"
    assert u.project_access_key == "k"


def test_api_access_check(monkeypatch):
    u.no_auth = True
    assert u.api_access_check(None) is True
    u.no_auth = False
    monkeypatch.setenv("PROJECT_ACCESS_KEY", "secret")
    u.project_access_key = "secret"
    req = type("R", (), {"headers": {"X-LURAWI-API-KEY": "secret"}})()
    assert u.api_access_check(req) is True
    req2 = type("R", (), {"headers": {"X-LURAWI-API-KEY": "wrong"}})()
    assert u.api_access_check(req2) is False


def test_encrypt_decrypt(monkeypatch):
    monkeypatch.delenv("LLMServiceDataAccessKey", raising=False)
    assert u.encrypt_ifavailable("hello") == "hello"
    assert u.decrypt_ifavailable("hello") == "hello"
    # round trip with a key
    import base64

    key = base64.b64encode(b"a" * 32).decode()
    monkeypatch.setenv("LLMServiceDataAccessKey", key)
    enc = u.encrypt_ifavailable("secret data")
    assert enc != "secret data"
    dec = u.decrypt_ifavailable(enc)
    assert dec == "secret data"


def test_encrypt_content_infile():
    import base64
    import os

    key = base64.b64decode(base64.b64encode(b"a" * 32))
    path = u._encrypt_content(key, "text", infile=True)
    assert os.path.exists(path)
    os.remove(path)


def test_time2str():
    assert u.time2str(0).startswith("0 second")
    assert "day" in u.time2str(86400)
    assert "hour" in u.time2str(3600)
    assert "minute" in u.time2str(60)
    assert "second" in u.time2str(5)
    assert u.time2str(90061) == "1 day 1 hour 1 minute 1 second"


def test_calc_token_size_and_cut_string():
    assert u.calc_token_size("hello world") > 0
    assert u.cut_string("hello world", n_tokens=5000) == "hello world"
    assert u.cut_string("a" * 5000, n_tokens=1) != ""
    # single-token path
    assert u.cut_string("a") != ""


def test_sticky_cookie(monkeypatch):
    u._set_stickyness_cookie({"k": "v"})
    assert u.get_stickyness_cookie() == {"k": "v"}
    # expired -> None
    import time as _t

    u._aws_sticky_cookie = ({"k": "v"}, _t.time() - 20)
    assert u.get_stickyness_cookie() is None


def test_write_http_response_headers_and_cookie():
    u._aws_sticky_cookie = None
    r = u.write_http_response(200, {"status": "success"}, headers={"X-Test": "abc"})
    assert r.headers.get("content-type") is not None
    assert r.headers.get("X-Test") == "abc"
    r.set_cookie("k", "v")  # must not crash
    assert r.headers.get("content-type") is not None


def test_decode_json_field():
    data = {"a_json": '{"x": 1}', "plain": "v"}
    out = u.decode_json_field(data)
    assert out["a"] == {"x": 1}
    assert out["plain"] == "v"
    # invalid json -> skipped
    out2 = u.decode_json_field({"bad_json": "{not json"})
    assert "bad" not in out2


def test_dev_stream_handler():
    assert u.get_dev_stream_handler() is None
    u.set_dev_stream_handler("handler")
    assert u.get_dev_stream_handler() == "handler"
    u.set_dev_stream_handler("other")
    assert u.get_dev_stream_handler() == "other"
    u.set_dev_stream_handler(None)
    assert u.get_dev_stream_handler() is None


def test_check_type():
    assert u.check_type(3, "int") is True
    assert u.check_type("hi", "str") is True
    assert u.check_type([], "list") is True
    assert u.check_type({}, "dict") is True
    assert u.check_type(1.5, "float") is True
    assert u.check_type(True, "bool") is True
    assert u.check_type("x", "int") is False
    assert u.check_type("x", "NotAType") is False


def test_is_valid_url():
    assert u.is_valid_url("https://example.com") is True
    assert u.is_valid_url("http://localhost:8080/path?q=1") is True
    assert u.is_valid_url("ftp://example.com") is True
    assert u.is_valid_url("not a url") is False


# ---------- storage (local paths) ----------


def test_get_content_from_azure_storage_local(tmp_path):
    p = tmp_path / "f.json"
    p.write_text('{"a": 1}')
    assert u.get_content_from_azure_storage(str(p)) == '{"a": 1}'
    # missing file -> None
    assert u.get_content_from_azure_storage(str(tmp_path / "nope")) is None


def test_aget_content_from_azure_storage_local(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("hello")
    content = asyncio.run(u.aget_content_from_azure_storage(str(p)))
    assert content == "hello"


def test_save_content_to_azure_storage_local(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("data")
    dst = tmp_path / "dst.txt"
    assert u.save_content_to_azure_storage(str(dst), str(src)) is True
    assert dst.read_text() == "data"


def test_asave_content_to_azure_storage_local(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("data")
    dst = tmp_path / "dst.txt"
    result = asyncio.run(u.asave_content_to_azure_storage(str(dst), str(src)))
    assert result is True
    assert dst.read_text() == "data"


def test_get_content_from_aws_s3_local(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("awsdata")
    assert u.get_content_from_aws_s3(str(p)) == "awsdata"


# ---------- network ----------


def test_aget_data_from_url(http_server):
    status, result = asyncio.run(u.aget_data_from_url({}, f"{http_server}/x"))
    assert status == 200
    assert result == {"ok": True}


def test_aget_data_from_url_error():
    status, err = asyncio.run(u.aget_data_from_url({}, "http://127.0.0.1:1/nope"))
    assert status is None
    assert err is not None


def test_apost_payload_to_url(http_server):
    status, result = asyncio.run(u.apost_payload_to_url({}, f"{http_server}/post", {"a": 1}))
    assert status == 200
    assert result == {"posted": True}


def test_apost_payload_to_url_put(http_server):
    status, _ = asyncio.run(u.apost_payload_to_url({}, f"{http_server}/put", {}, use_put=True))
    assert status == 200


def test_apost_payload_to_url_error():
    status, err = asyncio.run(u.apost_payload_to_url({}, "http://127.0.0.1:1/x", {}))
    assert status is None
    assert err is not None


def test_apost_data_to_url(http_server):
    status, result = asyncio.run(u.apost_data_to_url({}, f"{http_server}/data", {"a": "b"}))
    assert status == 200
    assert result == {"posted": True}


def test_apatch_data_to_url(http_server):
    status, _ = asyncio.run(u.apatch_data_to_url({}, f"{http_server}/patch", {}))
    assert status == 200


def test_aremove_data_from_url(http_server):
    status, _ = asyncio.run(u.aremove_data_from_url({}, f"{http_server}/del", {}))
    assert status == 200


def test_post_payload_to_url_error():
    status, err = u.post_payload_to_url("http://127.0.0.1:1/x", {})
    assert status is None
    assert err is not None


def test_post_payload_to_url_put_error():
    status, err = u.post_payload_to_url("http://127.0.0.1:1/x", {}, use_put=True)
    assert status is None
    assert err is not None


def test_get_remote_file_size_error():
    assert u.get_remote_file_size("http://127.0.0.1:1/x") == -1


def test_adownload_file_to_temp_error():
    with pytest.raises(ValueError):
        asyncio.run(u.adownload_file_to_temp("http://127.0.0.1:1/huge"))


# ---------- azure / aws storage branches (mocked clients) ----------


def test_get_content_from_azure_storage_blob(monkeypatch, tmp_path):
    class FakeBlob:
        def download_blob(self):
            class Resp:
                def content_as_text(self):
                    return '{"from": "azure"}'

            return Resp()

        def upload_blob(self, data, overwrite=True):
            self._uploaded = True

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "BlobClient", FakeBlobClient)
    assert u.get_content_from_azure_storage("f.json") == '{"from": "azure"}'


def test_aget_content_from_azure_storage_blob(monkeypatch):
    class FakeBlob:
        async def download_blob(self):
            class Resp:
                async def readall(self):
                    return b"azure-async"

            return Resp()

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "AsyncBlobClient", FakeBlobClient)
    assert asyncio.run(u.aget_content_from_azure_storage("f")) == b"azure-async"


def test_save_content_to_azure_storage_blob(monkeypatch, tmp_path):
    class FakeBlob:
        def upload_blob(self, data, overwrite=True):
            self._uploaded = True

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "BlobClient", FakeBlobClient)
    src = tmp_path / "s.txt"
    src.write_text("x")
    assert u.save_content_to_azure_storage("d.txt", str(src)) is True


def test_asave_content_to_azure_storage_blob(monkeypatch, tmp_path):
    class FakeBlob:
        async def upload_blob(self, data, overwrite=True):
            self._uploaded = True

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "AsyncBlobClient", FakeBlobClient)
    src = tmp_path / "s.txt"
    src.write_text("x")
    assert asyncio.run(u.asave_content_to_azure_storage("d.txt", str(src))) is True


def test_get_content_from_aws_s3_branch(monkeypatch):
    class FakeS3:
        def download_fileobj(self, bucket, key, io):
            io.write('{"from": "s3"}')

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setattr(u.boto3, "client", lambda svc: FakeS3())
    assert u.get_content_from_aws_s3("key", container="bucket") == '{"from": "s3"}'


# ---------- network success paths ----------


def test_post_payload_to_url_success(http_server):
    status, result = u.post_payload_to_url(f"{http_server}/post", {"a": 1})
    assert status == 200
    assert result == {"posted": True}


def test_get_remote_file_size_success(http_server):
    assert u.get_remote_file_size(f"{http_server}/x") == 5


def test_adownload_file_to_temp_success(http_server, tmp_path):
    path = asyncio.run(u.adownload_file_to_temp(f"{http_server}/file"))
    assert os.path.exists(path)
    os.remove(path)


def test_apost_payload_to_url_sticky(http_server):
    status, _ = asyncio.run(
        u.apost_payload_to_url({}, f"{http_server}/post", {}, use_stickyness=True)
    )
    assert status == 200
    assert u._aws_sticky_cookie is not None
    u._aws_sticky_cookie = None


def test_write_http_response_with_cookies():
    import time as _t

    u._aws_sticky_cookie = ({"sid": "abc"}, _t.time())
    r = u.write_http_response(200, {"s": "ok"})
    assert r.headers.get("set-cookie") is not None
    u._aws_sticky_cookie = None


def test_aget_data_from_url_error_path():
    status, err = asyncio.run(u.aget_data_from_url({}, "http://127.0.0.1:1/x"))
    assert status is None


def test_apost_data_to_url_error():
    status, err = asyncio.run(u.apost_data_to_url({}, "http://127.0.0.1:1/x", {}))
    assert status is None


def test_apatch_data_to_url_error():
    status, err = asyncio.run(u.apatch_data_to_url({}, "http://127.0.0.1:1/x", {}))
    assert status is None


def test_aremove_data_from_url_error():
    status, err = asyncio.run(u.aremove_data_from_url({}, "http://127.0.0.1:1/x", {}))
    assert status is None


def test_get_content_from_azure_storage_error(monkeypatch):
    class FakeBlob:
        def download_blob(self):
            raise Exception("boom")

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "BlobClient", FakeBlobClient)
    assert u.get_content_from_azure_storage("f.json") is None


def test_aget_content_from_azure_storage_error(monkeypatch):
    class FakeBlob:
        async def download_blob(self):
            raise Exception("boom")

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "AsyncBlobClient", FakeBlobClient)
    assert asyncio.run(u.aget_content_from_azure_storage("f")) is None


def test_save_content_to_azure_storage_error(monkeypatch, tmp_path):
    class FakeBlob:
        def upload_blob(self, data, overwrite=True):
            raise Exception("boom")

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "BlobClient", FakeBlobClient)
    src = tmp_path / "s.txt"
    src.write_text("x")
    assert u.save_content_to_azure_storage("d", str(src)) is False


def test_asave_content_to_azure_storage_error(monkeypatch, tmp_path):
    class FakeBlob:
        async def upload_blob(self, data, overwrite=True):
            raise Exception("boom")

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "AsyncBlobClient", FakeBlobClient)
    src = tmp_path / "s.txt"
    src.write_text("x")
    assert asyncio.run(u.asave_content_to_azure_storage("d", str(src))) is False


def test_get_content_from_aws_s3_error(monkeypatch):
    class FakeS3:
        def download_fileobj(self, bucket, key, io):
            raise Exception("boom")

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setattr(u.boto3, "client", lambda svc: FakeS3())
    assert u.get_content_from_aws_s3("key", container="bucket") is None


def test_get_content_from_azure_storage_as_binary(monkeypatch):
    class FakeBlob:
        def download_blob(self):
            class Resp:
                def content_as_bytes(self):
                    return b"bytes"

            return Resp()

    class FakeBlobClient:
        @staticmethod
        def from_connection_string(conn_str, container_name, blob_name):
            return FakeBlob()

    monkeypatch.setenv("AzureWebJobsStorage", "conn")
    monkeypatch.setattr(u, "BlobClient", FakeBlobClient)
    assert u.get_content_from_azure_storage("f", as_binary=True) == b"bytes"


def test_get_content_from_aws_s3_binary(monkeypatch):
    class FakeS3:
        def download_fileobj(self, bucket, key, io):
            io.write(b"bytes")

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setattr(u.boto3, "client", lambda svc: FakeS3())
    assert u.get_content_from_aws_s3("key", container="bucket", as_binary=True) == b"bytes"


def test_aget_data_from_url_404_retry(monkeypatch):
    class Resp:
        status = 404

        async def json(self):
            return None

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def get(self, url, ssl=True):
            class Ctx:
                def __init__(self, resp):
                    self.resp = resp

                async def __aenter__(self):
                    return self.resp

                async def __aexit__(self, *a):
                    return False

            return Ctx(Resp())

    monkeypatch.setattr(u.aiohttp, "ClientSession", lambda **kw: FakeSession())
    status, result = asyncio.run(u.aget_data_from_url({}, "http://x/404"))
    assert status == 404
    assert result is None
