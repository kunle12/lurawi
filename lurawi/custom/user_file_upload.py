import os
import urllib.request
import json

from azure.storage.blob import BlobClient
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger

SUPPORTED_DATATYPES = ["json", "txt", "png", "jpeg"]


class user_file_upload(CustomBehaviour):
    """!@brief prompted user to upload a file.
    Example:
    ["custom", { "name": "user_file_upload",
                 "args": {
                            "prompt":"Enter your name",
                            "type": "json",
                            "output":"GUESTNAME",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    user file upload save file either locally where the bot is running or under a specified Azure storage path.
    The string of the saved file path is stored in the knowledge base with a specified output.
    """

    def __init__(self, kb, details):
        super().__init__(kb, details)
        self.content_types = ["text"]
        self.data_key = None

    async def run(self):
        prompt = ""
        if "type" not in self.details:
            logger.error("user_file_upload: expect a type arg.")
            await self.failed()
            return

        content_types = self.details["type"].split("|")
        logger.debug(content_types)
        if not all(key in SUPPORTED_DATATYPES for key in content_types):
            logger.error(
                f"user_file_upload: expect a type in 'json', 'txt', 'png' or 'jpeg', but got {self.details['type']}"
            )
            await self.failed()
            return

        self.data_key = self.parse_simple_input(key="output", check_for_type="str")

        if self.data_key is None:
            logger.error("send_data_to_url: missing or invalid output(str)")
            await self.failed()
            return

        self.content_types = content_types

        if "prompt" in self.details:
            prompt = self.details["prompt"]
            if isinstance(prompt, list) and len(prompt) == 2:
                to_say, keys = prompt
                if isinstance(keys, list):
                    for key in keys:
                        if key in self.kb:
                            to_say = to_say.replace("{}", str(self.kb[key]), 1)
                        else:
                            _key = str(key).replace("_", " ")
                            to_say = to_say.replace("{}", _key, 1)
                    prompt = to_say
                else:
                    sample = ["hello {}, good {}", ["KB_KEY1", "KB_KEY2"]]
                    logger.error(
                        f"user_file_upload: invalid prompt {prompt}). action should be of form- {sample}"
                    )
                    prompt = ""
            elif not isinstance(prompt, str):
                logger.error(f"user_file_upload: invalid prompt {prompt}).")
                prompt = ""

        if prompt == "":
            prompt = "Please upload your file"

        self.register_for_user_message_updates()
        await self.message(prompt)

    async def on_user_message_update(self, context):
        if not context.activity.attachments or len(context.activity.attachments) == 0:
            await self.message("please upload your file")
            return

        if len(context.activity.attachments) > 1:
            await self.message(
                "currently we support one file upload at a time, only the first file is taken"
            )

        if await self._handle_incoming_attachment(context):
            await self.succeeded()
        else:
            await self.failed()

    async def _handle_incoming_attachment(self, turn_context):
        """
        Handle attachments uploaded by users. The bot receives an Attachment in an Activity.
        The activity has a List of attachments.
        Not all channels allow users to upload files. Some channels have restrictions
        on file type, size, and other attributes. Consult the documentation for the channel for
        more information. For example Skype's limits are here
        <see ref="https://support.skype.com/en/faq/FA34644/skype-file-sharing-file-types-size-and-time-limits"/>.
        :param turn_context:
        :return:
        """
        return await self._download_attachment_and_write(
            turn_context.activity.attachments[0]
        )

    async def _download_attachment_and_write(self, attachment):
        """
        Retrieve the attachment via the attachment's contentUrl.
        :param attachment:
        :return: Dict: keys "filename", "local_path"
        """
        try:
            response = urllib.request.urlopen(attachment.content_url)
            headers = response.info()

            logger.error(f"uploaded file type {headers['content-type']}")
            # if self.content_types not in headers['content-type']:
            # If user uploads JSON file, this prevents it from being written as
            # "{"type":"Buffer","data":[123,13,10,32,32,34,108lurawi.."
            if headers["content-type"] == "application/json":
                if self.content_types[0] != "json":
                    await self.message(
                        f"uploaded file {attachment.name} is not the expected file type"
                    )
                    return False
                data = bytes(json.load(response)["data"])
            else:
                fn, ext = os.path.splitext(attachment.name)
                if ext[1:] not in self.content_types:
                    await self.message(
                        f"uploaded file {attachment.name} is not the expected file type"
                    )
                    return False
                data = response.read()
        except Exception as exception:
            await self.message(
                f"Error receiving file {attachment.name}, error={exception}"
            )
            return False

        try:
            fn, ext = os.path.splitext(attachment.name)
            i = 1
            if "AzureWebJobsStorage" in os.environ:
                connect_string = os.environ["AzureWebJobsStorage"]
                local_filename = attachment.name
                blob = BlobClient.from_connection_string(
                    conn_str=connect_string,
                    container_name="botuploads",
                    blob_name=attachment.name,
                )
                while blob.exists():
                    local_filename = f"{fn}-{i}{ext}"
                    blob = BlobClient.from_connection_string(
                        conn_str=connect_string,
                        container_name="botuploads",
                        blob_name=local_filename,
                    )
                    i += 1
                blob.upload_blob(data)
            else:
                local_filename = os.path.join(os.getcwd(), attachment.name)
                while os.path.exists(local_filename):
                    local_filename = os.path.join(os.getcwd(), f"{fn}-{i}{ext}")
                    i += 1

                with open(local_filename, "wb") as out_file:
                    out_file.write(data)
        except Exception as e:
            await self.message(
                f"unable to save uploaded file {attachment.name}, error={e}"
            )
            return False

        await self.message(f"Successfully received file {attachment.name}")
        self.kb[self.data_key] = local_filename
        return True
