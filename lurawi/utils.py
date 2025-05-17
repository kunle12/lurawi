import aiofiles as aiof
import aiohttp
import base64
import boto3
import jwt
import logging
import os
import re
import random
import requests
import simplejson as json
import string
import tiktoken
import time

from azure.storage.blob.aio import BlobClient as AsyncBlobClient
from azure.storage.blob import BlobClient
from Crypto.Cipher import AES
from fastapi import Request
from fastapi.responses import JSONResponse
from io import StringIO, BytesIO
from typing import Dict, AsyncIterable

logger = logging.getLogger("lurawi")
logger.addHandler(logging.StreamHandler())

logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))

no_auth = False
ssl_verify = True
in_dev = False
_tiktokeniser = None
_aws_sticky_cookie = None
_dev_stream_handler = None

project_name = None
project_access_key = None

PYTHON_TYPE_MAPPING = {
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "tuple": tuple,
    "dict": dict,
    "set": set,
    "bool": bool,
    "None": type(None),
    "complex": complex,
    "bytes": bytes,
    "bytearray": bytearray,
    "range": range,
    "frozenset": frozenset,
}


def is_indev() -> bool:
    return in_dev


def get_project_settings() -> bool:
    global project_name
    global project_access_key

    if "PROJECT_NAME" in os.environ:
        project_name = os.environ["PROJECT_NAME"]
    else:
        logger.error("Missing PROJECT_NAME environment variable.")
        return False

    if "PROJECT_ACCESS_KEY" in os.environ:
        project_access_key = os.environ["PROJECT_ACCESS_KEY"]
    else:
        logger.error("Missing PROJECT_ACCESS_KEY environment variable.")
        return False

    return True


def api_access_check(req: Request, project: str = None) -> bool:
    if no_auth:
        return True

    api_key = req.headers.get("X-LURAWI-API-KEY")

    if api_key:
        return api_key == project_access_key
    else:
        auth_bearer = req.headers.get("Authorization")
        if auth_bearer and auth_bearer.startswith("Bearer"):
            auth_bearer = auth_bearer[7:]
            # TODO check bearer token


def encrypt_ifavailable(data):
    if "LLMServiceDataAccessKey" not in os.environ:
        logging.warning(
            "encrypt_ifavailable: missing data access keys, return original data"
        )
        return data

    encdata = None
    try:
        secret_key = base64.b64decode(os.environ["LLMServiceDataAccessKey"])
        encdata = _encrypt_content(secret_key, data, infile=False)
        encdata = base64.encodebytes(encdata)
    except Exception as _:
        logging.error("unable to encrypt data, return original data")
        return data

    return encdata.decode()


def decrypt_ifavailable(data):
    if "LLMServiceDataAccessKey" not in os.environ:
        logging.warning(
            "decrypt_ifavailable: missing data access keys, return original data"
        )
        return data

    decdata = None
    try:
        decdata = data.encode()
        decdata = base64.decodebytes(decdata)
        secret_key = base64.b64decode(os.environ["LLMServiceDataAccessKey"])
        decdata = _decrypt_content(secret_key, decdata)
    except Exception as _:
        logging.error("unable to decrypt data, return original data")
        return data

    return decdata.decode()


def _decrypt_content(key, content):
    text = None
    nonce = content[:16]
    tag = content[16:32]
    data = content[32:]
    try:
        cipher = AES.new(key, AES.MODE_EAX, nonce)
        text = cipher.decrypt_and_verify(data, tag)
    except Exception as e:
        logging.error(f"unable to descrypt content, error {e}")

    # print(f"decrypted text {text}")
    return text


def _encrypt_content(key, content, infile=True):
    # use the cipher to encrypt the padded message
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(content.encode("utf-8"))

    if infile:
        tmp_file_name = f"/tmp/{''.join(random.SystemRandom().choice(string.ascii_letters+string.digits) for _ in range(8))}.enc"

        file_out = open(tmp_file_name, "wb")
        [file_out.write(x) for x in (cipher.nonce, tag, ciphertext)]
        file_out.close()
        return tmp_file_name
    else:
        enc_data = cipher.nonce + tag + ciphertext
        return enc_data


def time2str(time_int):
    timestr = ""
    tm = time_int
    if tm >= 86400:
        blk = int(tm / 86400)
        timestr = f"{blk} day{'s' if blk > 1 else ''}"
        tm = tm % 86400
    if tm >= 3600:
        blk = int(tm / 3600)
        timestr += f" {blk} hour{'s' if blk > 1 else ''}"
        tm = tm % 3600

    if tm >= 60:
        blk = int(tm / 60)
        timestr += f" {blk} minute{'s' if blk > 1 else ''}"
        tm = tm % 60
    tm = int(tm)
    timestr += f" {tm} second{'s' if tm > 1 else ''}"

    return timestr.lstrip()


def _get_tiktoken_tokenizer(tokenizer_name="cl100k_base", logger=None, state=None):
    tokenizer = tiktoken.get_encoding(tokenizer_name)
    return tokenizer


def calc_token_size(text: str) -> int:
    global _tiktokeniser

    if not _tiktokeniser:
        _tiktokeniser = _get_tiktoken_tokenizer()
    return len(_tiktokeniser.encode(text))


def cut_string(s, n_tokens=2500, logger=None, state=None):
    # cuts of string based on number of tokens
    global _tiktokeniser

    if not _tiktokeniser:
        _tiktokeniser = _get_tiktoken_tokenizer()
    encoded_string = _tiktokeniser.encode(s)
    if len(encoded_string) == 1:
        return _tiktokeniser.decode_single_token_bytes(encoded_string)
    elif len(encoded_string) <= n_tokens:
        return _tiktokeniser.decode(encoded_string)
    else:
        return _tiktokeniser.decode(encoded_string[:n_tokens])


def get_stickyness_cookie():
    global _aws_sticky_cookie
    if _aws_sticky_cookie:
        if (
            _aws_sticky_cookie[1] - time.time() <= 10
        ):  # ignore cookie is older than 10 sec
            return _aws_sticky_cookie[0]
        _aws_sticky_cookie = None
    return None


def _set_stickyness_cookie(cookies):
    global _aws_sticky_cookie
    _aws_sticky_cookie = (cookies, time.time())


def get_content_from_azure_storage(
    filepath, container="llamservice_data", as_binary=False
):
    content = None
    if "AzureWebJobsStorage" in os.environ:
        connect_string = os.environ["AzureWebJobsStorage"]
        try:
            blob = BlobClient.from_connection_string(
                conn_str=connect_string, container_name=container, blob_name=filepath
            )
            if as_binary:
                content = blob.download_blob().content_as_bytes()
            else:
                content = blob.download_blob().content_as_text()
        except Exception as e:
            logger.error(f"unable to load '{filepath}' from blob storage: error {e}")
    elif os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"unable to load '{filepath}' from local drive: error {e}")

    return content


async def aget_content_from_azure_storage(filepath, container="llmservicedata"):
    content = None
    if "AzureWebJobsStorage" in os.environ:
        connect_string = os.environ["AzureWebJobsStorage"]
        try:
            blob = AsyncBlobClient.from_connection_string(
                conn_str=connect_string, container_name=container, blob_name=filepath
            )
            stream = await blob.download_blob()
            content = await stream.readall()
        except Exception as e:
            logger.error(f"unable to load '{filepath}' from blob storage: error {e}")
    elif os.path.exists(filepath):
        try:
            async with aiof.open(filepath, "r") as f:
                content = await f.read()
        except Exception as e:
            logger.error(f"unable to load '{filepath}' from local drive: error {e}")

    return content


def save_content_to_azure_storage(filepath, content_file, container="llmservice_data"):
    if "AzureWebJobsStorage" in os.environ:
        connect_string = os.environ["AzureWebJobsStorage"]
        try:
            blob = BlobClient.from_connection_string(
                conn_str=connect_string, container_name=container, blob_name=filepath
            )
            with open(content_file, "rb") as data:
                blob.upload_blob(data, overwrite=True)
        except Exception as err:
            logger.error(
                f"save_content_to_storage: unable to save '{filepath}' in the blob storage: error {err}"
            )
            return False
    else:
        try:
            with open(filepath, "wb") as f, open(content_file, "rb") as d:
                content = d.read()
                f.write(content)
        except Exception as err:
            logger.error(
                f"save_content_to_storage: unable to save '{filepath}' on the local drive: error {err}"
            )
            return False

    return True


async def asave_content_to_azure_storage(
    filepath, content_file, container="llmservice_data"
):
    if "AzureWebJobsStorage" in os.environ:
        connect_string = os.environ["AzureWebJobsStorage"]
        try:
            blob = AsyncBlobClient.from_connection_string(
                conn_str=connect_string, container_name=container, blob_name=filepath
            )
            async with aiof.open(content_file, "rb") as data:
                await blob.upload_blob(data, overwrite=True)
        except Exception as err:
            logger.error(
                f"save_content_to_storage: unable to save '{filepath}' in the blob storage: error {err}"
            )
            return False
    else:
        try:
            async with aiof.open(filepath, "wb") as f, aiof.open(
                content_file, "rb"
            ) as d:
                content = await d.read()
                await f.write(content)
        except Exception as err:
            logger.error(
                f"save_content_to_storage: unable to save '{filepath}' on the local drive: error {err}"
            )
            return False

    return True


def get_content_from_aws_s3(filepath, container="llamservice_data", as_binary=False):
    content = None
    if "AWS_ACCESS_KEY_ID" in os.environ and "AWS_SECRET_ACCESS_KEY" in os.environ:
        s3_client = boto3.client("s3")
        try:
            blobio = None
            if as_binary:
                blobio = BytesIO()
                s3_client.download_fileobj(container, filepath, blobio)
            else:
                blobio = StringIO()
                s3_client.download_fileobj(container, filepath, blobio)
            content = blobio.read()
        except Exception as e:
            logger.error(f"unable to load '{filepath}' from s3 storage: error {e}")
    elif os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"unable to load '{filepath}' from local drive: error {e}")

    return content


async def aget_data_from_url(headers, url):
    retries = 0
    url_status = 404
    try:
        result = None
        async with aiohttp.ClientSession(headers=headers) as session:
            while url_status == 404 and retries < 4:
                async with session.get(url, ssl=ssl_verify) as r:
                    url_status = r.status
                    if url_status == 404:
                        retries += 1
                        continue
                    try:
                        result = await r.json()
                    except Exception as _:
                        result = None
            return url_status, result
    except Exception as err:
        logger.error(
            f"aget_data_from_url: failed to retrieve data from url {url}: error {err}"
        )
        return None, err


async def apost_payload_to_url(
    headers, url, payload, usePut=False, use_stickyness=False
):
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            if usePut:
                async with session.put(url, json=payload, ssl=ssl_verify) as r:
                    result = None
                    try:
                        result = await r.json()
                        if use_stickyness:
                            _set_stickyness_cookie(r.cookies)
                    except Exception as _:
                        result = None
                    return r.status, result
            else:
                async with session.post(url, json=payload, ssl=ssl_verify) as r:
                    result = None
                    try:
                        result = await r.json()
                        if use_stickyness:
                            _set_stickyness_cookie(r.cookies)
                    except Exception as _:
                        result = None
                    return r.status, result
    except Exception as err:
        logger.error(
            f"apost_payload_to_url: failed to post json payload to url {url}: error {err}"
        )
        return None, err


async def apost_data_to_url(headers, url, data, usePut=False, use_stickyness=False):
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            if usePut:
                async with session.put(url, data=data, ssl=ssl_verify) as r:
                    result = None
                    try:
                        result = await r.json()
                        if use_stickyness:
                            _set_stickyness_cookie(r.cookies)
                    except Exception as _:
                        result = None
                    return r.status, result
            else:
                async with session.post(url, data=data, ssl=ssl_verify) as r:
                    result = None
                    try:
                        result = await r.json()
                        if use_stickyness:
                            _set_stickyness_cookie(r.cookies)
                    except Exception as _:
                        result = None
                    return r.status, result
    except Exception as err:
        logger.error(
            f"apost_data_to_url: failed to post data to url {url}: error {err}"
        )
        return None, err


async def apatch_data_to_url(headers, url, payload):
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.patch(url, json=payload, ssl=ssl_verify) as r:
                result = None
                return r.status, result
    except Exception as err:
        logger.error(
            f"apatch_data_to_url: failed to send patch data to url {url}: error {err}"
        )
        return None, err


async def aremove_data_from_url(headers, url, payload):
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.delete(url, json=payload, ssl=ssl_verify) as r:
                result = None
                try:
                    result = await r.json()
                except Exception as _:
                    result = None
                return r.status, result
    except Exception as err:
        logger.error(
            f"aremove_data_from_url: failed to remove data from url {url}: error {err}"
        )
        return None, err


def post_payload_to_url(url, payload, headers=None, usePut=False):
    if headers is None:
        headers = {"Content-Type": "application/json"}
    try:
        if usePut:
            r = requests.put(url, headers=headers, json=payload, verify=ssl_verify)
        else:
            r = requests.post(url, headers=headers, json=payload, verify=ssl_verify)
    except Exception as err:
        logging.error(f"unable to send post request, error {err}")
        return None, err

    result = None
    logging.debug(f"successfully sending request")
    try:
        result = r.json()
    except Exception as _:
        result = None
    return r.status_code, result


def write_http_response(status, body_dict, headers={}):
    response = JSONResponse(status_code=status, content=body_dict)
    if headers:
        response.headers = headers
    cookies = get_stickyness_cookie()
    if cookies:
        for c in cookies:
            response.set_cookie(key=c, value=cookies[c].value)
    return response


def decode_json_field(data: Dict) -> Dict:
    new_dict = {}
    for k, v in data.items():
        if k.endswith("_json"):
            try:
                new_dict[k[:-5]] = json.loads(v)
            except Exception as err:
                logger.error("get_documents: unable to load {k}: {err}")
        else:
            new_dict[k] = v
    return new_dict


def get_dev_stream_handler():
    global _dev_stream_handler
    return _dev_stream_handler


def set_dev_stream_handler(handler):
    global _dev_stream_handler
    if _dev_stream_handler and handler is not None:
        logger.warning("set_dev_stream_handler: handler is not empty, replace.")
    _dev_stream_handler = handler


def check_type(value: any, type_info: str) -> bool:
    """
    Check if a value is an instance or subtype of the specified type
    """
    expected_type = PYTHON_TYPE_MAPPING.get(type_info.lower())

    if expected_type is None:
        try:
            expected_type = eval(type_info)
        except Exception as _:
            return False

    return isinstance(value, expected_type)


class DataStreamHandler(object):
    def __init__(self, response) -> None:
        self._response = response

    async def stream_generator(self) -> AsyncIterable[str]:
        async for chunk in self._response:
            content = chunk.choices[0].delta.content or ""
            if content:
                content = content.replace("\n", "<br/>")
                yield f"data: {content}\n\n"
