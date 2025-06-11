"""Utility functions for the Lurawi system.

This module provides a collection of utility functions for various operations including:
- Authentication and access control
- Encryption and decryption
- Time formatting
- Token calculation and string manipulation
- Azure and AWS storage operations
- HTTP request handling
- JSON processing
- Data streaming

These utilities are used throughout the Lurawi system to provide common functionality
and abstract away implementation details of various operations.
"""

import base64
import time
import logging
import os
import string
import random
import aiofiles as aiof
import aiohttp
import boto3
import requests
import simplejson as json
import tiktoken

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
    """Check if the system is running in development mode.

    Returns:
        bool: True if running in development mode, False otherwise
    """
    return in_dev


def get_project_settings() -> bool:
    """Load project settings from environment variables.

    Loads PROJECT_NAME and PROJECT_ACCESS_KEY from environment variables
    and stores them in global variables.

    Returns:
        bool: True if settings were loaded successfully, False otherwise
    """

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


def api_access_check(req: Request, project: str = "") -> bool:
    """Check if an API request is authorized.

    Verifies that the X-LURAWI-API-KEY header matches the project access key.

    Args:
        req: The FastAPI request object
        project: Optional project name (not currently used)

    Returns:
        bool: True if the request is authorized, False otherwise
    """
    if no_auth:
        return True

    api_key = req.headers.get("X-LURAWI-API-KEY")

    return api_key == project_access_key


def encrypt_ifavailable(data):
    """Encrypt data if encryption key is available.

    Args:
        data: The data to encrypt

    Returns:
        str: Encrypted data as a base64-encoded string if encryption is available,
             otherwise the original data
    """
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
    """Decrypt data if decryption key is available.

    Args:
        data: The encrypted data as a base64-encoded string

    Returns:
        str: Decrypted data if decryption is available,
             otherwise the original data
    """
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
    """Decrypt content using AES encryption.

    Args:
        key: The decryption key
        content: The encrypted content

    Returns:
        bytes: Decrypted content as bytes
    """
    text = None
    nonce = content[:16]
    tag = content[16:32]
    data = content[32:]
    try:
        cipher = AES.new(key, AES.MODE_EAX, nonce)
        text = cipher.decrypt_and_verify(data, tag)
    except Exception as e:
        logging.error("unable to descrypt content, error %s", e)

    # print(f"decrypted text {text}")
    return text


def _encrypt_content(key, content, infile=True):
    """Encrypt content using AES encryption.

    Args:
        key: The encryption key
        content: The content to encrypt
        infile: If True, save encrypted content to a temporary file
                If False, return encrypted content as bytes

    Returns:
        str or bytes: Path to temporary file containing encrypted content if infile=True,
                      otherwise encrypted content as bytes
    """
    # use the cipher to encrypt the padded message
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(content.encode("utf-8"))

    if infile:
        tmp_file_name = f"/tmp/{''.join(random.SystemRandom().choice(string.ascii_letters+string.digits) for _ in range(8))}.enc"

        file_out = open(tmp_file_name, "wb")
        [file_out.write(x) for x in (cipher.nonce, tag, ciphertext)]
        file_out.close()
        return tmp_file_name

    enc_data = cipher.nonce + tag + ciphertext
    return enc_data


def time2str(time_int):
    """Convert time in seconds to a human-readable string.

    Args:
        time_int: Time in seconds

    Returns:
        str: Human-readable time string (e.g., "2 days 3 hours 45 minutes 30 seconds")
    """
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
    """Get a tiktoken tokenizer instance.

    Args:
        tokenizer_name: Name of the tokenizer to use
        logger: Optional logger instance (not used)
        state: Optional state object (not used)

    Returns:
        tiktoken.Encoding: Tokenizer instance
    """
    tokenizer = tiktoken.get_encoding(tokenizer_name)
    return tokenizer


def calc_token_size(text: str) -> int:
    """Calculate the number of tokens in a text string.

    Args:
        text: The text to tokenize

    Returns:
        int: Number of tokens in the text
    """
    global _tiktokeniser

    if not _tiktokeniser:
        _tiktokeniser = _get_tiktoken_tokenizer()
    return len(_tiktokeniser.encode(text))


def cut_string(s, n_tokens=2500, logger=None, state=None):
    """Cut a string to a maximum number of tokens.

    Args:
        s: The string to cut
        n_tokens: Maximum number of tokens to keep
        logger: Optional logger instance (not used)
        state: Optional state object (not used)

    Returns:
        str: The original string if it's shorter than n_tokens,
             otherwise the string cut to n_tokens
    """
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
    """Get the AWS sticky session cookie if available and not expired.

    Returns:
        dict or None: Cookie dictionary if available and not expired, None otherwise
    """
    global _aws_sticky_cookie
    if _aws_sticky_cookie:
        if (
            _aws_sticky_cookie[1] - time.time() <= 10
        ):  # ignore cookie is older than 10 sec
            return _aws_sticky_cookie[0]
        _aws_sticky_cookie = None
    return None


def _set_stickyness_cookie(cookies):
    """Set the AWS sticky session cookie with current timestamp.

    Args:
        cookies: Cookie dictionary to store
    """
    global _aws_sticky_cookie
    _aws_sticky_cookie = (cookies, time.time())


def get_content_from_azure_storage(
    filepath, container="llamservice_data", as_binary=False
):
    """Retrieve content from Azure Blob Storage or local file system.

    Args:
        filepath: Path to the file to retrieve
        container: Azure Blob Storage container name
        as_binary: If True, return content as bytes, otherwise as text

    Returns:
        str or bytes or None: File content if successful, None otherwise
    """
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
            logger.error("unable to load '%s' from blob storage: error %s", filepath, e)
    elif os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except Exception as e:
            logger.error("unable to load '%s' from local drive: error %s", filepath, e)

    return content


async def aget_content_from_azure_storage(filepath, container="llmservicedata"):
    """Asynchronously retrieve content from Azure Blob Storage or local file system.

    Args:
        filepath: Path to the file to retrieve
        container: Azure Blob Storage container name

    Returns:
        str or bytes or None: File content if successful, None otherwise
    """
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
            logger.error("unable to load '%s' from blob storage: error %s", filepath, e)
    elif os.path.exists(filepath):
        try:
            async with aiof.open(filepath, "r") as f:
                content = await f.read()
        except Exception as e:
            logger.error("unable to load '%s' from local drive: error %s", filepath, e)

    return content


def save_content_to_azure_storage(filepath, content_file, container="llmservice_data"):
    """Save content to Azure Blob Storage or local file system.

    Args:
        filepath: Path where the file should be saved
        content_file: Path to the file containing the content to save
        container: Azure Blob Storage container name

    Returns:
        bool: True if content was saved successfully, False otherwise
    """
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
                "save_content_to_storage: unable to save '%s' in the blob storage: error %s",
                filepath,
                err,
            )
            return False
    else:
        try:
            with open(filepath, "wb") as f, open(content_file, "rb") as d:
                content = d.read()
                f.write(content)
        except Exception as err:
            logger.error(
                "save_content_to_storage: unable to save '%s' on the local drive: error %s",
                filepath,
                err,
            )
            return False

    return True


async def asave_content_to_azure_storage(
    filepath, content_file, container="llmservice_data"
):
    """Asynchronously save content to Azure Blob Storage or local file system.

    Args:
        filepath: Path where the file should be saved
        content_file: Path to the file containing the content to save
        container: Azure Blob Storage container name

    Returns:
        bool: True if content was saved successfully, False otherwise
    """
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
                "save_content_to_storage: unable to save '%s' in the blob storage: error %s",
                filepath,
                err,
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
                "save_content_to_storage: unable to save '%s' on the local drive: error %s",
                filepath,
                err,
            )
            return False

    return True


def get_content_from_aws_s3(filepath, container="llamservice_data", as_binary=False):
    """Retrieve content from AWS S3 or local file system.

    Args:
        filepath: Path to the file to retrieve
        container: S3 bucket name
        as_binary: If True, return content as bytes, otherwise as text

    Returns:
        str or bytes or None: File content if successful, None otherwise
    """
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
            logger.error("unable to load '%s' from s3 storage: error %s", filepath, e)
    elif os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except Exception as e:
            logger.error("unable to load '%s' from local drive: error %s", filepath, e)

    return content


async def aget_data_from_url(headers, url):
    """Asynchronously retrieve data from a URL with retry logic.

    Args:
        headers: HTTP headers to include in the request
        url: URL to retrieve data from

    Returns:
        tuple: (status_code, response_data) if successful,
               (None, error) if an error occurred
    """
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
            "aget_data_from_url: failed to retrieve data from url %s: error %s",
            url,
            err,
        )
        return None, err


async def apost_payload_to_url(
    headers, url, payload, use_put=False, use_stickyness=False
):
    """Asynchronously post JSON payload to a URL.

    Args:
        headers: HTTP headers to include in the request
        url: URL to post data to
        payload: JSON payload to send
        use_put: If True, use PUT method instead of POST
        use_stickyness: If True, store cookies for sticky sessions

    Returns:
        tuple: (status_code, response_data) if successful,
               (None, error) if an error occurred
    """
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            if use_put:
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
            "apost_payload_to_url: failed to post json payload to url %s: error %s",
            url,
            err,
        )
        return None, err


async def apost_data_to_url(headers, url, data, use_put=False, use_stickyness=False):
    """Asynchronously post form data to a URL.

    Args:
        headers: HTTP headers to include in the request
        url: URL to post data to
        data: Form data to send
        use_put: If True, use PUT method instead of POST
        use_stickyness: If True, store cookies for sticky sessions

    Returns:
        tuple: (status_code, response_data) if successful,
               (None, error) if an error occurred
    """
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            if use_put:
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
            "apost_data_to_url: failed to post data to url %s: error %s", url, err
        )
        return None, err


async def apatch_data_to_url(headers, url, payload):
    """Asynchronously send a PATCH request to a URL.

    Args:
        headers: HTTP headers to include in the request
        url: URL to send the PATCH request to
        payload: JSON payload to send

    Returns:
        tuple: (status_code, None) if successful,
               (None, error) if an error occurred
    """
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.patch(url, json=payload, ssl=ssl_verify) as r:
                result = None
                return r.status, result
    except Exception as err:
        logger.error(
            "apatch_data_to_url: failed to send patch data to url %s: error %s",
            url,
            err,
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
            "aremove_data_from_url: failed to remove data from url %s: error %s",
            url,
            err,
        )
        return None, err


def post_payload_to_url(url, payload, headers=None, use_put=False):
    if headers is None:
        headers = {"Content-Type": "application/json"}
    try:
        if use_put:
            r = requests.put(url, headers=headers, json=payload, verify=ssl_verify)
        else:
            r = requests.post(url, headers=headers, json=payload, verify=ssl_verify)
    except Exception as err:
        logging.error("unable to send post request, error %s", err)
        return None, err

    result = None
    logging.debug("successfully sending request")
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
                logger.error("get_documents: unable to load %s: %s", k, err)
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
    """Handler for streaming data from LLM responses.

    This class processes streaming responses from language models
    and formats them for Server-Sent Events (SSE).
    """

    def __init__(self, response) -> None:
        """Initialize a new DataStreamHandler.

        Args:
            response: The streaming response object from the language model
        """
        self._response = response

    async def stream_generator(self) -> AsyncIterable[str]:
        """Generate formatted SSE data from streaming response.

        Yields:
            str: Formatted SSE data chunks with HTML line breaks
        """
        async for chunk in self._response:
            content = chunk.choices[0].delta.content or ""
            if content:
                content = content.replace("\n", "<br/>")
                yield f"data: {content}\n\n"
