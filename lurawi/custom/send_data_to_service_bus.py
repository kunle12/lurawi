"""
Custom behaviour for sending data to Azure Service Bus.

This module defines the `send_data_to_service_bus` class, which allows the
system to send messages to a specified Azure Service Bus queue using a
connection string and a JSON payload.
"""

import os
import simplejson as json
from lurawi.utils import logger
from lurawi.custom_behaviour import CustomBehaviour
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient


class send_data_to_service_bus(CustomBehaviour):
    """!@brief Sends a JSON payload as a message to an Azure Service Bus queue.

    This custom behaviour connects to an Azure Service Bus using a provided
    connection string (or an environment variable) and sends a JSON payload
    to a specified queue. It supports resolving payload values from the
    knowledge base.

    Args:
        connect_str (str, optional): The Azure Service Bus connection string.
                                     If not provided, it attempts to use the
                                     `ServiceBusConnStr` environment variable.
                                     Can be a direct string or a knowledge base key.
        queue (str): The name of the Service Bus queue to which the message
                     will be sent. Can be a direct string or a knowledge base key.
        payload (dict): The JSON payload to be sent as the message body.
                        Values within the dictionary can be knowledge base keys
                        or nested template structures `["template {}", ["KB_KEY"]]`.
        success_action (list, optional): An action to execute if the message
                                         is successfully sent (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if sending the
                                        message fails (e.g., `["play_behaviour", "next"]`).

    Example:
    ["custom", { "name": "send_data_to_service_bus",
                 "args": {
                            "connect_str" : "Endpoint=sb://...",
                            "queue": "myqueue",
                            "payload": { "event_type": "user_registered", "user_id": "USER_ID_KB_KEY" },
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the Service Bus message sending logic.

        This method retrieves and validates the connection string, queue name,
        and payload. It resolves payload values from the knowledge base,
        establishes a connection to Azure Service Bus, and sends the message.
        It handles success and failure actions accordingly.
        """
        connect_str = None
        if "connect_str" in self.details and isinstance(
            self.details["connect_str"], str
        ):
            connect_str = self.details["connect_str"]
        elif "ServiceBusConnStr" in os.environ and isinstance(
            os.environ["ServiceBusConnStr"], str
        ):
            connect_str = os.environ["ServiceBusConnStr"]

        if connect_str is None:
            logger.error(
                "send_data_to_service_bus: missing or invalid connect_str (not found in args or environment variable 'ServiceBusConnStr'). Aborting."
            )
            await self.failed()
            return

        if connect_str in self.kb:  # Resolve connect_str from KB if it's a key
            connect_str = self.kb[connect_str]

        queue = self.parse_simple_input(key="queue", check_for_type="str")

        if queue is None:
            logger.error(
                "send_data_to_service_bus: missing or invalid 'queue' argument (expected a string). Aborting."
            )
            await self.failed()
            return

        payload = self.parse_simple_input(key="payload", check_for_type="dict")

        if payload is None:
            logger.error(
                "send_data_to_service_bus: missing or invalid 'payload' argument (expected a dictionary). Aborting."
            )
            await self.failed()
            return

        # Deep copy the payload to avoid modifying the original details
        payload_resolved = json.loads(json.dumps(payload))
        for k, v in payload_resolved.items():
            if isinstance(v, str) and v in self.kb:
                value = self.kb[v]
                if isinstance(value, list) and len(value) > 1:
                    # Handle nested template: ["content {}", ["key"]]
                    keys = value[1]
                    if not isinstance(keys, list):
                        logger.error(
                            "send_data_to_service_bus: invalid payload: invalid composite value format for key '%s'",
                            k,
                        )
                        await self.failed()
                        return
                    content = value[0]
                    for key in keys:
                        if key in self.kb:
                            content = content.replace("{}", str(self.kb[key]), 1)
                        else:
                            _key = str(key).replace("_", " ")
                            content = content.replace("{}", _key, 1)
                    payload_resolved[k] = content
                else:
                    payload_resolved[k] = value
            # If v is not a string or not in kb, it's used as a literal value

        try:
            async with ServiceBusClient.from_connection_string(
                conn_str=connect_str, logging_enable=True
            ) as servicebus_client:
                # Get a Queue Sender object to send messages to the queue
                sender = servicebus_client.get_queue_sender(queue_name=queue)
                async with sender:
                    # Send one message
                    message = ServiceBusMessage(json.dumps(payload_resolved))
                    await sender.send_messages(message)
                    logger.info(
                        "send_data_to_service_bus: Message sent successfully to queue '%s'.",
                        queue,
                    )
                    await self.succeeded()
        except Exception as err:
            logger.error(
                "send_data_to_service_bus: Failed to send message to Service Bus: %s",
                err,
            )
            self.kb["ERROR_MESSAGE"] = str(err)  # Store error message in KB
            await self.failed()
            self.kb["ERROR_MESSAGE"] = ""  # Clear error message after handling
