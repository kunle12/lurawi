"""
Custom behaviour for querying the knowledge base with various conditions.

This module defines the `query_knowledgebase` class, which allows the system
to retrieve specific data from its knowledge base based on a `knowledge_key`,
an optional `query_arg` (which can be a direct value or a key to another
knowledge base entry), and an optional `phrase_match` flag for fuzzy matching.
"""

import simplejson as json
from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class query_knowledgebase(CustomBehaviour):
    """!@brief Retrieves data from the knowledge base based on specified conditions.

    This custom behaviour provides flexible querying capabilities for the
    knowledge base. It can retrieve values directly by a `knowledge_key`,
    or by a nested key within a dictionary identified by `knowledge_key`
    and `query_arg`/`query_key`. It also supports phrase matching for fuzzy
    lookups.

    Args:
        knowledge_key (str): The primary key in the knowledge base to query.
                             This key must exist.
        query_arg (str or dict, optional): An argument used to refine the query.
                                           - If a string, it's treated as a key
                                             within the `knowledge_key`'s value.
                                             Can also be a knowledge base key.
                                           - If a dictionary, it's expected to
                                             contain a `query_key` to extract
                                             the actual query argument.
                                           If not provided, the value of `knowledge_key`
                                           itself is returned.
        query_key (str, optional): Used in conjunction with `query_arg` when
                                   `query_arg` is a dictionary. Specifies the
                                   key within `query_arg` to use as the actual
                                   query. Can also be a knowledge base key.
        phrase_match (bool, optional): If `True`, performs a case-insensitive
                                       phrase match within the 'phrases' list
                                       of items under `knowledge_key`. If a match
                                       is found, the entire matched item is returned.
                                       Defaults to `False`.
        query_output (str, optional): The knowledge base key under which the
                                      retrieved data will be stored. Defaults to
                                      "QUERY_OUTPUT".
        phrase_match_key (str, optional): If `phrase_match` is `True` and a match
                                          is found, the key of the matched item
                                          (e.g., "known_person_name") will be stored
                                          under this knowledge base key. Defaults to
                                          "PHRASE_MATCH_KEY".
        success_action (list, optional): An action to execute if the query is
                                         successful (e.g., `["play_behaviour", "2"]`).
        failed_action (list, optional): An action to execute if the query fails
                                        (e.g., `["play_behaviour", "next"]`).

    Example: Retrieve a known person by name using phrase match:
    ["custom", { "name": "query_knowledgebase",
                 "args": {
                            "phrase_match": True,
                            "knowledge_key": "known_people",
                            "query_arg": "USER_INPUT_NAME",
                            "query_key": "known_people",
                            "query_output" : "MATCHED_PERSON_DATA",
                            "phrase_match_key": "MATCHED_PERSON_KEY",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    async def run(self):
        """
        Executes the knowledge base query logic.

        This method validates the `knowledge_key` and then proceeds based on
        the presence and type of `query_arg` and `phrase_match`. It resolves
        keys and values from the knowledge base as needed, performs the lookup
        (direct key access or phrase matching), and stores the result in the
        knowledge base, triggering success or failure actions.
        """
        found = None
        if isinstance(self.details, dict) and "knowledge_key" in self.details:
            knowledge_key = self.details["knowledge_key"]
            if knowledge_key not in self.kb:
                logger.error(
                    "query_knowledgebase: cannot find %s key in the knowledge base. Aborting.",
                    self.details['knowledge_key']
                )
                await self.failed()
                return

            input_arg = ""
            if "query_arg" in self.details:
                knowledge_variable = self.kb[knowledge_key]
                # Attempt to load knowledge_variable as JSON if it's a string
                if isinstance(knowledge_variable, str):
                    try:
                        knowledge_variable = json.loads(knowledge_variable)
                    except json.JSONDecodeError:
                        logger.error(
                            "query_knowledgebase: knowledge[%s] is a string but not valid JSON. Aborting.",
                            knowledge_key
                        )
                        await self.failed()
                        return
                elif not isinstance(knowledge_variable, dict):
                    logger.error(
                        "query_knowledgebase: knowledge[%s] is not a dictionary. Got %s. Aborting.",
                        knowledge_key, type(knowledge_variable)
                    )
                    await self.failed()
                    return

                query_key = ""
                query_arg = self.details["query_arg"]

                if "query_key" in self.details:
                    query_key = self.details["query_key"]

                # Resolve query_arg from knowledge base if it's a key
                if isinstance(query_arg, str) and query_arg in self.kb:
                    query_arg = self.kb[query_arg]

                if isinstance(query_arg, dict):
                    if query_key in query_arg:
                        input_arg = query_arg[query_key]
                        if isinstance(input_arg, list):
                            if len(input_arg) == 0:
                                logger.error(
                                    "query_knowledgebase: invalid input argument list (empty). Aborting."
                                )
                                await self.failed()
                                return
                            else:
                                input_arg = input_arg[0] # Take the first item if it's a list
                    else:
                        logger.error(
                            "query_knowledgebase: query_arg dict '%s' does not contain query key '%s'. Aborting.",
                            self.details.get('query_arg'), self.details.get('query_key')
                        )
                        await self.failed()
                        return
                else:
                    input_arg = query_arg

                if "phrase_match" in self.details and self.details["phrase_match"]:
                    # Perform phrase matching
                    for t, act in knowledge_variable.items(): # Use .items() for Python 3
                        if "phrases" in act and isinstance(act["phrases"], list):
                            if input_arg.lower() in [p.lower() for p in act["phrases"]]:  # force to lower cases.
                                found = act
                                if "phrase_match_key" in self.details and isinstance(
                                    self.details["phrase_match_key"], str
                                ):
                                    self.kb[self.details["phrase_match_key"]] = t
                                else:
                                    self.kb["PHRASE_MATCH_KEY"] = t # Default key for phrase match
                                break
                        else:
                            logger.warning(
                                "query_knowledgebase: no 'phrases' list found in kb['%s']['%s'] for phrase matching.",
                                knowledge_key, t
                            )
                else:
                    # Direct key lookup
                    if input_arg in knowledge_variable:
                        found = knowledge_variable[input_arg]
            else:
                # If no query_arg, return the entire knowledge_key value
                input_arg = knowledge_key
                found = self.kb[knowledge_key]

            if found is None:
                self.kb["UNKNOWN_QUERY"] = input_arg
                logger.info("query_knowledgebase: No match found for query '%s'. Storing in UNKNOWN_QUERY.", input_arg)
                await self.failed()
            else:
                self.kb["KNOWN_QUERY"] = input_arg
                if "query_output" in self.details and isinstance(
                    self.details["query_output"], str
                ):
                    self.kb[self.details["query_output"]] = found
                else:
                    self.kb["QUERY_OUTPUT"] = found # Default output key
                logger.debug("query_knowledgebase: Query successful. Result: %s", found)
                await self.succeeded()
        else:
            logger.error("query_knowledgebase: 'knowledge_key' argument is required. Aborting.")
            await self.failed()
