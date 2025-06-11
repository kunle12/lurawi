import simplejson as json
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class query_knowledgebase(CustomBehaviour):
    """!@brief retrieve from the knowledge base with the following conditions
    if query_arg is a dict, then knowledge base[knowledge_key][query_arg[query_key]];
    if query_arg is a string, then the knowledge base[knowledge_key][query_arg];
    if query_arg is not provided, then the knowledge base[knowledge_key];
    Example:
    ["custom", { "name": "query_knowledgebase",
                 "args": {
                            "phrase_match": True,
                            "knowledge_key": "known_people",
                            "query_arg": "USER_COMMAND_DATA",
                            "query_key": "known_people",
                            "query_output" : "KNOWN_PERSON",
                            "phrase_match_key": "KNOWN_QUERY_KEY",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    @note query_output, success_action and failed_action are optional.
    @note if phrase_match, query key is determined through phrase match
    """

    async def run(self):
        found = None
        if isinstance(self.details, dict) and "knowledge_key" in self.details:
            knowledge_key = self.details["knowledge_key"]
            if knowledge_key not in self.kb:
                logger.error(
                    "query_knowledgebase: cannot find %s key in the knowledge base.",
                    self.details['knowledge_key']
                )
                await self.failed()
                return

            input_arg = ""
            if "query_arg" in self.details:
                knowledge_variable = self.kb[knowledge_key]
                if isinstance(knowledge_variable, str):
                    try:
                        knowledge_variable = json.loads(knowledge_variable)
                    except Exception as _:
                        logger.error(
                            "query_knowledgebase: knowledge[%s] is not a dict",
                            knowledge_key
                        )
                        await self.failed()
                        return
                elif not isinstance(knowledge_variable, dict):
                    logger.error(
                        "query_knowledgebase: knowledge[%s] is not a dict",
                        knowledge_key
                    )
                    await self.failed()
                    return

                query_key = ""
                query_arg = self.details["query_arg"]

                if "query_key" in self.details:
                    query_key = self.details["query_key"]

                if query_arg in self.kb:  # arg is a key in the knowledge
                    query_arg = self.kb[query_arg]

                if isinstance(query_arg, dict):
                    if query_key in query_arg:
                        input_arg = query_arg[query_key]
                        if isinstance(input_arg, list):
                            if len(input_arg) == 0:
                                logger.error(
                                    "query_knowledgebase: invalid input argument list (empty)"
                                )
                                await self.failed()
                                return
                            else:
                                input_arg = input_arg[0]
                    else:
                        logger.error(
                            "query_knowledgebase: query_arg dict %s does not contain query key %s",
                            self.details['query_arg'], self.details['query_key']
                        )
                        await self.failed()
                        return
                else:
                    input_arg = query_arg

                if "phrase_match" in self.details and self.details["phrase_match"]:
                    for t, act in knowledge_variable.iteritems():
                        if "phrases" in act:
                            if (
                                input_arg.lower() in act["phrases"]
                            ):  # force to lower cases.
                                found = act
                                if "phrase_match_key" in self.details and isinstance(
                                    self.details["phrase_match_key"], str
                                ):
                                    self.kb[self.details["phrase_match_key"]] = t
                                else:
                                    self.kb["PHRASE_MATCH_KEY"] = t
                                break
                        else:
                            logger.error(
                                "query_knowledgebase: no phrase in kb['%s']['%s']",
                                {knowledge_key}, t
                            )
                else:
                    if input_arg in knowledge_variable:
                        found = knowledge_variable[input_arg]
            else:
                input_arg = knowledge_key
                found = self.kb[knowledge_key]

            if found is None:
                self.kb["UNKNOWN_QUERY"] = input_arg
                await self.failed()
            else:
                self.kb["KNOWN_QUERY"] = input_arg
                if "query_output" in self.details and isinstance(
                    self.details["query_output"], str
                ):
                    self.kb[self.details["query_output"]] = found
                else:
                    self.kb["QUERY_OUTPUT"] = found
                await self.succeeded()
        else:
            logger.error("query_knowledgebase: must have a knowledge key value")
            await self.failed()
