"""
Custom behaviour for prompting a user to upload a file and handling the upload.

This module defines the `user_file_upload` class, which allows the system
to request a file from the user, validate its type, and save it either
locally or to Azure Blob Storage, storing the file path in the knowledge base.
"""

import os
import urllib.request
import json

from typing import Dict
from azure.storage.blob import BlobClient
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger

# Supported file types for upload
SUPPORTED_DATATYPES = ["json", "txt", "png", "jpeg", "pdf", "docx"]


class user_file_upload(CustomBehaviour):
    """!@brief Prompts the user to upload a file and handles the file upload.

    This custom behaviour requests a file from the user, validates its type
    against a list of supported data types, and then saves the file. Files
    can be saved either locally where the bot is running or to a specified
    Azure Blob Storage path. The path to the saved file is then stored in
    the knowledge base under a designated output key.

    Args:
        prompt (str or list, optional): The message to display to the user
                                        when requesting the file upload.
                                        - If a string, it's the direct prompt text.
                                        - If a list `["template {}", ["KB_KEY"]]`,
                                          it's a template string with placeholders
                                          `{}` and a list of knowledge base keys
                                          whose values will replace the placeholders.
                                        Defaults to "Please upload your file".
        type (str): A pipe-separated string of allowed file extensions (e.g., "json|txt|png").
                    Only files matching these types will be accepted.
        output (str): The knowledge base key under which the path to the
                      saved file will be stored.
        success_action (list, optional): An action to execute if the file
                                         is successfully uploaded and saved.
        failed_action (list, optional): An action to execute if the upload
                                        or saving process fails.

    Example:
    ["custom", { "name": "user_file_upload",
                 "args": {
                            "prompt":"Please upload your resume (PDF or DOCX):",
                            "type": "pdf|docx",
                            "output":"RESUME_FILE_PATH",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    def __init__(self, kb, details):
        """
        Initializes the user_file_upload custom behaviour.

        Args:
            kb (dict): The knowledge base dictionary.
            details (dict): A dictionary containing the arguments for this behaviour.
        """
        super().__init__(kb, details)
        self.content_types: list[str] = []  # List of allowed file extensions
        self.data_key: str | None = None  # Key to store the saved file path

    async def run(self):
        """
        Executes the file upload prompting logic.

        This method validates the 'type' and 'output' arguments. It constructs
        the prompt message (resolving placeholders if the prompt is a template),
        registers for user message updates, and sends the prompt to the user.
        """
        prompt = ""
        if "type" not in self.details:
            logger.error(
                "user_file_upload: 'type' argument is required (e.g., 'json|txt'). Aborting."
            )
            await self.failed()
            return

        content_types_str = self.details["type"]
        if isinstance(content_types_str, str):
            self.content_types = [
                ext.strip().lower() for ext in content_types_str.split("|")
            ]
        else:
            logger.error(
                "user_file_upload: 'type' argument must be a string. Got %s. Aborting.",
                type(content_types_str),
            )
            await self.failed()
            return

        logger.debug("user_file_upload: Expected content types: %s", self.content_types)
        if not all(key in SUPPORTED_DATATYPES for key in self.content_types):
            logger.error(
                "user_file_upload: Unsupported file type(s) specified in 'type'. Supported: {', '.join(SUPPORTED_DATATYPES)}. Got: {self.details['type']}. Aborting."
            )
            await self.failed()
            return

        self.data_key = self.details.get("output")

        if not self.data_key or not isinstance(self.data_key, str):
            logger.error(
                "user_file_upload: missing or invalid 'output' argument (expected a string). Aborting."
            )
            await self.failed()
            return

        if "prompt" in self.details:
            prompt_arg = self.details["prompt"]
            if isinstance(prompt_arg, list) and len(prompt_arg) == 2:
                # Handle template prompt: ["template {}", ["KB_KEY"]]
                to_say, keys = prompt_arg
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
                        "user_file_upload: Invalid prompt format %s. Expected format: %s",
                        prompt_arg,
                        sample,
                    )
                    prompt = ""
            elif isinstance(prompt_arg, str):
                prompt = prompt_arg
            else:
                logger.error(
                    "user_file_upload: Invalid prompt type %s. Expected string or list.",
                    type(prompt_arg),
                )
                prompt = ""

        if prompt == "":
            prompt = "Please upload your file"

        self.register_for_user_message_updates()  # Register to receive the user's file upload
        await self.message(prompt)  # Send the prompt to the user

    async def on_user_message_update(self, context: Dict):
        """
        Callback method invoked when a user message update (containing attachments) is received.

        This method is triggered after the `user_file_upload` behaviour has prompted
        the user and is awaiting a file. It checks for attachments, handles multiple
        uploads (taking only the first), and attempts to download and save the file.

        Args:
            context (Dict): The user message data context, typically containing
                            `activity.attachments` with file metadata.
        """
        if not context.activity.attachments or len(context.activity.attachments) == 0:
            await self.message("Please upload your file.")
            return

        if len(context.activity.attachments) > 1:
            await self.message(
                "Currently we support one file upload at a time; only the first file will be processed."
            )

        if await self._handle_incoming_attachment(context):
            await self.succeeded()
        else:
            await self.failed()

    async def _handle_incoming_attachment(self, turn_context) -> bool:
        """
        Handles attachments uploaded by users.

        The bot receives an Attachment in an Activity. The activity has a List of attachments.
        This method processes the first attachment found.

        Args:
            turn_context: The turn context containing the activity with attachments.

        Returns:
            bool: True if the attachment was successfully downloaded and written, False otherwise.
        """
        if turn_context.activity.attachments:
            return await self._download_attachment_and_write(
                turn_context.activity.attachments[0]
            )
        return False

    async def _download_attachment_and_write(self, attachment) -> bool:
        """
        Retrieves the attachment via the attachment's contentUrl and saves it.

        This method downloads the file from the provided content URL, validates
        its content type against the allowed types, and then saves it either
        locally or to Azure Blob Storage. It handles potential filename conflicts.

        Args:
            attachment: The attachment object containing contentUrl and name.

        Returns:
            bool: True if the file was successfully downloaded and written, False otherwise.
        """
        try:
            response = urllib.request.urlopen(attachment.content_url)
            headers = response.info()

            file_content_type = (
                headers.get("content-type", "").split(";")[0].strip().lower()
            )
            logger.debug(
                "user_file_upload: Uploaded file content type: %s", file_content_type
            )

            # Determine file extension from attachment name or content type
            fn, ext = os.path.splitext(attachment.name)
            actual_ext = ext[1:].lower() if ext else ""

            # Special handling for JSON content type if it's a buffer
            data = None
            if file_content_type == "application/json":
                if "json" not in self.content_types:
                    await self.message(
                        f"Uploaded file '{attachment.name}' is a JSON file, but 'json' is not an expected file type."
                    )
                    return False
                try:
                    # Assuming JSON content might be a buffer representation
                    json_data = json.load(response)
                    if (
                        isinstance(json_data, dict)
                        and "type" in json_data
                        and json_data["type"] == "Buffer"
                        and "data" in json_data
                    ):
                        data = bytes(json_data["data"])
                    else:
                        data = json.dumps(json_data).encode(
                            "utf-8"
                        )  # Re-encode if it's just JSON content
                except Exception as e:
                    logger.error(
                        "user_file_upload: Failed to parse JSON attachment: %s", e
                    )
                    await self.message(f"Error parsing JSON file {attachment.name}.")
                    return False
            else:
                # For other file types, check against allowed extensions
                if actual_ext and actual_ext not in self.content_types:
                    await self.message(
                        f"Uploaded file '{attachment.name}' has an unsupported extension '.{actual_ext}'. Expected types: {', '.join(self.content_types)}."
                    )
                    return False
                elif (
                    not actual_ext
                    and file_content_type.split("/")[-1] not in self.content_types
                ):
                    # Fallback check if no extension but content type matches
                    await self.message(
                        f"Uploaded file '{attachment.name}' has an unsupported content type '{file_content_type}'. Expected types: {', '.join(self.content_types)}."
                    )
                    return False
                data = response.read()

            if data is None:
                await self.message(
                    f"Could not read data from uploaded file {attachment.name}."
                )
                return False

        except urllib.error.URLError as url_err:
            logger.error(
                "user_file_upload: URL Error receiving file %s: %s",
                attachment.name,
                url_err,
            )
            await self.message(f"Error receiving file {attachment.name}: {url_err}")
            return False
        except Exception as exception:
            logger.error(
                "user_file_upload: Unexpected error receiving file %s: %s",
                attachment.name,
                exception,
            )
            await self.message(f"Error receiving file {attachment.name}: {exception}")
            return False

        try:
            # Determine filename and handle conflicts
            base_filename, file_extension = os.path.splitext(attachment.name)
            if not file_extension and file_content_type:
                # Try to infer extension from content type if missing from filename
                mime_to_ext = {
                    "application/json": ".json",
                    "text/plain": ".txt",
                    "image/png": ".png",
                    "image/jpeg": ".jpeg",
                    "application/pdf": ".pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                }
                file_extension = mime_to_ext.get(file_content_type, "")
                if not file_extension:
                    logger.warning(
                        "user_file_upload: Could not infer file extension from content type '%s'.",
                        file_content_type,
                    )

            local_filename = f"{base_filename}{file_extension}"
            i = 1

            if "AzureWebJobsStorage" in os.environ:
                connect_string = os.environ["AzureWebJobsStorage"]
                container_name = "botuploads"  # Standard container for uploads
                blob_name = local_filename

                blob = BlobClient.from_connection_string(
                    conn_str=connect_string,
                    container_name=container_name,
                    blob_name=blob_name,
                )
                while blob.exists():
                    local_filename = f"{base_filename}-{i}{file_extension}"
                    blob_name = local_filename
                    blob = BlobClient.from_connection_string(
                        conn_str=connect_string,
                        container_name=container_name,
                        blob_name=blob_name,
                    )
                    i += 1
                blob.upload_blob(
                    data, overwrite=True
                )  # Overwrite if it's the same name after conflict resolution
                saved_path = f"azureblob://{container_name}/{blob_name}"
            else:
                # Save locally
                upload_dir = os.path.join(
                    os.getcwd(), "uploads"
                )  # Create an 'uploads' directory
                os.makedirs(upload_dir, exist_ok=True)  # Ensure directory exists

                local_file_path = os.path.join(upload_dir, local_filename)
                while os.path.exists(local_file_path):
                    local_filename = f"{base_filename}-{i}{file_extension}"
                    local_file_path = os.path.join(upload_dir, local_filename)
                    i += 1

                with open(local_file_path, "wb") as out_file:
                    out_file.write(data)
                saved_path = local_file_path

        except Exception as e:
            logger.error(
                "user_file_upload: Unable to save uploaded file %s: %s",
                attachment.name,
                e,
            )
            await self.message(
                f"Unable to save uploaded file {attachment.name}, error={e}"
            )
            return False

        await self.message(f"Successfully received file {attachment.name}")
        self.kb[self.data_key] = saved_path
        logger.info("user_file_upload: File saved to: %s", saved_path)
        return True
