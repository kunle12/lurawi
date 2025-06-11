import os
import simplejson as json
from lurawi.utils import logger
from lurawi.custom_behaviour import CustomBehaviour
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient


class send_data_to_service_bus(CustomBehaviour):
    """!@brief create an asset request in the asset registry.
    Example:
    ["custom", { "name": "send_data_to_service_bus",
                 "args": {
                            "connect_str" : "https://localhost:4848/newuser",
                            "queue": "service bus queue name",
                            "payload": { "key": "some data" },
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note this custom provide a generic call to a specific connect_str to post data
    """

    async def run(self):
        if "connect_str" not in self.details or not isinstance(
            self.details["connect_str"], str
        ):
            if "ServiceBusConnStr" not in os.environ or not isinstance(
                os.environ["ServiceBusConnStr"], str
            ):
                logger.error("send_data_to_service_bus: missing or invalid connect_str")
                await self.failed()
                return
            connect_str = os.environ["ServiceBusConnStr"]
        else:
            connect_str = self.details["connect_str"]

        if connect_str in self.kb:
            connect_str = self.kb[connect_str]

        queue = self.parse_simple_input(key="queue", check_for_type="str")

        if queue is None:
            logger.error("send_data_to_service_bus: missing or invalid queue(str)")
            await self.failed()
            return

        payload = self.parse_simple_input(key="payload", check_for_type="dict")

        if payload is None:
            logger.error("send_data_to_service_bus: missing or invalid payload(dict)")
            await self.failed()
            return

        payload = json.loads(json.dumps(payload))
        for k, v in payload.items():
            if v in self.kb:
                value = self.kb[v]
                if isinstance(value, list) and len(value) > 1:
                    keys = value[1]
                    if not isinstance(keys, list):
                        logger.error(
                            "send_data_to_service_bus: invalid payload: invalid composite value format"
                        )
                        await self.failed()
                        return
                    content = value[0]
                    for key in keys:
                        if key in self.knowledge:
                            content = content.replace("{}", str(self.knowledge[key]), 1)
                        else:
                            _key = str(key).replace("_", " ")
                            content = content.replace("{}", _key, 1)
                    payload[k] = content
                else:
                    payload[k] = value

        async with ServiceBusClient.from_connection_string(
            conn_str=connect_str, logging_enable=True
        ) as servicebus_client:
            # Get a Queue Sender object to send messages to the queue
            sender = servicebus_client.get_queue_sender(queue_name=queue)
            async with sender:
                # Send one message
                message = ServiceBusMessage(json.dumps(payload))
                try:
                    await sender.send_messages(message)
                    await self.succeeded()
                except Exception as _:
                    await self.failed()
