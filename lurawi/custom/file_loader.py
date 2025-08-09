"""
This module provides the `file_loader` custom behavior for loading various file types
into the knowledge base, including text, PDF, and image formats.
"""

# pylint: disable=broad-exception-caught, import-error

import os
import base64

from io import BytesIO
from PIL import Image
from pdf2image import convert_from_path

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger, is_valid_url, adownload_file_to_temp

SUPPORTED_FILE_TYPES = [
    "text",  # include txt, md, csv text file format
    "pdf",
    "image",
]


class file_loader(CustomBehaviour):
    """
    A custom behavior class designed to load content from various file types
    (text, PDF, PNG, JPEG) and store it in the knowledge base.

    This class supports loading local files and converting image and PDF
    content into base64 encoded strings suitable for use with image-based
    models or other applications requiring inline image data.

    Supported file types are defined in `SUPPORTED_FILE_TYPES`.

    Example Usage in a Workflow:
        ["custom", {
            "name": "file_loader",
            "args": {
                "file_location": "/path/to/the/file.txt",
                "file_type": "text",
                "output": "loaded_text_content",
                "success_action": ["play_behaviour", "next"],
                "failed_action": ["play_behaviour", "error_handler"]
            }
        }]

    Args:
        file_location (str): The absolute path to the file to be loaded.
        file_type (str): The type of the file. Must be one of "text", "pdf", "png", or "jpeg".
        output (str, optional): The key in the knowledge base where the loaded
                                content will be stored. Defaults to "LOADED_FILE_CONTENT".
        success_action (list, optional): Action to perform on successful file load.
        failed_action (list, optional): Action to perform on failed file load.
    """

    async def run(self):
        """
        Executes the file loading operation.

        This method parses the `file_location` and `file_type` from the
        behavior's details, validates them, and then proceeds to load the
        file content. The loaded content is stored in the knowledge base
        at the specified `output` key.

        For image and PDF files, content is converted to base64 encoded
        image URLs. Text files are read directly.

        Raises:
            Exception: If there is an error reading the file.
        """

        def _encode_image_base64(image: Image) -> str:
            """
            Encodes a PIL Image object into a base64 string.

            Args:
                image (Image): The PIL Image object to encode.
                format (Literal["PNG", "JPEG"], optional): The image format for encoding.
                                                            Defaults to "PNG".

            Returns:
                str: The base64 encoded string of the image.
            """
            buffer = BytesIO()
            image.save(buffer, "PNG")
            buffer.seek(0)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        file_type = self.parse_simple_input(key="file_type", check_for_type="str")

        if file_type is None or file_type not in SUPPORTED_FILE_TYPES:
            logger.error("file_loader: invalid file type %s. Aborting", file_type)
            await self.failed()
            return

        file_location = self.parse_simple_input(
            key="file_location", check_for_type="str"
        )

        downloaded_file = False

        if os.path.isfile(file_location):
            logger.debug("file_loader: loading file path %s", file_location)
        elif is_valid_url(file_location):
            try:
                file_location = await adownload_file_to_temp(url=file_location)
                downloaded_file = True
            except Exception as err:
                logger.error(
                    "file_loader: unable to download %s: %s", file_location, err
                )
                await self.failed()
                return
        else:
            logger.error("file_loader: invalid file path %s. Aborting", file_location)
            await self.failed()
            return

        output_location = "LOADED_FILE_CONTENT"

        if "output" in self.details and isinstance(self.details["output"], str):
            output_location = self.details["output"]

        try:
            if file_type == "text":
                with open(file=file_location, mode="r", encoding="utf-8") as f:
                    self.kb[output_location] = [{"type": "text", "text": f"{f.read()}"}]
            elif file_type == "image":
                image = Image.open(file_location)
                self.kb[output_location] = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{_encode_image_base64(image=image)}"
                        },
                    }
                ]
            elif file_type == "pdf":
                images = convert_from_path(file_location, fmt="png")
                # openai image upload str style
                openai_image_messages = []
                for image in images:
                    openai_image_messages.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{_encode_image_base64(image=image)}"
                            },
                        }
                    )
                self.kb[output_location] = openai_image_messages
        except Exception as err:
            if downloaded_file:
                os.remove(file_location)
            logger.error("file_loader: fail to read file %s: %s.", file_location, err)
            await self.failed()
            return

        if downloaded_file:
            os.remove(file_location)

        await self.succeeded()
