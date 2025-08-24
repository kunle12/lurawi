#! /usr/bin/env python3
"""
This module provides the BehaviourComposer class for composing a master behaviour file
from a directory of smaller JSON files. It handles loading, validating, and saving
behaviour definitions, including managing default behaviours and program variables.
"""

from __future__ import print_function
import os
import sys
import argparse
import simplejson as json


def print_error(*args, **kwargs):
    """Prints error messages to stderr."""
    print(*args, file=sys.stderr, **kwargs)


class BehaviourComposer(object):
    """
    Composes a master behaviour file from a directory of small JSON files.

    This class manages the loading, validation, and saving of behaviour definitions,
    including handling default behaviours, program variables, and asset URLs.
    """

    def __init__(self):
        """
        Initializes the BehaviourComposer with predefined behaviour keywords
        and master data structure.
        """
        self.behaviour_keywords = {
            "text": [str, list],
            "knowledge": [dict],
            "delay": [float, int],
            "custom": [str, dict],
            "select_behaviour": [str],
            "play_behaviour": [str],
            "random": [list],
            "calculate": [list],
            "compare": [dict],
            "comment": [str],
            "workflow_interaction": [str, dict],
        }
        self.master_data = {"default": "", "behaviours": []}
        self.found_default_behaviour = False
        self.knowledge_file = None
        self.data_dir = ""
        self.outputname = "behaviours-master.json"
        self.asset_url = None
        self.program_variables = {}

    def set_default_behaviour(self, name):
        """
        Sets the default behaviour for the master file.

        Args:
            name (str): The name of the behaviour to set as default.
        """
        self.master_data["default"] = name

    def set_output_name(self, name):
        """
        Sets the output file name for the master behaviour file.

        Args:
            name (str): The desired output file name.
        """
        self.outputname = name

    def set_asset_url(self, url):
        """
        Sets the base URL for image assets.

        Args:
            url (str): The base URL for assets.
        """
        self.asset_url = url

    def load_data_from_directory(self, path):
        """
        Loads behaviour data from JSON files within a specified directory.

        Args:
            path (str): The path to the directory containing behaviour JSON files.

        Returns:
            bool: True if a default behaviour is found and data is loaded, False otherwise.
        """
        if not os.path.isdir(path):
            print_error(f"Invalid data path {path}")
            return False

        self.data_dir = path
        for root, _, files in os.walk(path):
            if len(files) > 0 and not os.path.islink(root):
                for file in files:
                    if os.path.splitext(file)[1] != ".json":
                        continue
                    fpath = os.path.join(root, file)
                    (dname, data) = self.load_behaviours(fpath)
                    if data:
                        self.master_data["behaviours"].extend(data)
                        if not self.found_default_behaviour:
                            if self.master_data["default"] == "" and dname:
                                self.master_data["default"] = dname
                                self.found_default_behaviour = True
                            elif self.master_data["default"] in [
                                x["name"] for x in data
                            ]:
                                self.found_default_behaviour = True

        # consolidate variables
        for be in self.master_data["behaviours"]:
            if be["name"] != "__init__":
                continue
            default_action = be["actions"][0]
            if default_action[0][0] == "knowledge":
                default_action[0][1] = self.program_variables
                break

        if not self.found_default_behaviour:
            print_error(
                f"Unable to locate specified default behaviour {self.master_data['default']}."
            )
        return self.found_default_behaviour

    def load_behaviours(self, script):
        """
        Loads and validates behaviours from a single JSON script file.

        Args:
            script (str): The path to the JSON behaviour file.

        Returns:
            tuple: A tuple containing (default_behaviour_name, list_of_behaviours)
                   if valid, otherwise (None, None).
        """
        data = None
        valid = True
        if script is not None:
            try:
                f = open(script, "r", encoding="utf-8")
                data = json.load(f)
                f.close()
            except Exception as err:
                print_error(f"Unable to load behaviours file {script}, error {err}.")
                return (None, None)

        # TODO: validate knowledgebase file.
        if script.endswith("_knowledge.json"):
            self.knowledge_file = script
            return (None, None)

        try:
            default_demo = None
            if "default" in data:
                default_demo = data["default"]
                self.extract_variables_from_default(data)
            for be in data["behaviours"]:
                if "actions" not in be:
                    print_error(f"missing actions in behaviour {be['name']}")
                    valid = False
                    break
                for id_ac, ac in enumerate(be["actions"]):
                    for id_al, al in enumerate(ac):
                        if isinstance(al, list):
                            if len(al) % 2 != 0 or not self.validate_action_let(al):
                                valid = False
                                print_error(
                                    f"invalid actionlet in behaviour {be['name']} action {id_ac} index {id_al}."
                                )
                        else:
                            valid = False
                            print_error(
                                f"invalid behaviour {be['name']} action {id_ac} {al}."
                            )
        except Exception as _:
            print_error("the behaviour file contains unresolved errors.")
            valid = False

        if valid:
            return (default_demo, data["behaviours"])
        else:
            print_error(f"loaded behaviour file {script} is corrupted.")
            return (None, None)

    def validate_action_let(self, alet):
        """
        Validates a single actionlet within a behaviour.

        Args:
            alet (list): The actionlet to validate.

        Returns:
            bool: True if the actionlet is valid, False otherwise.
        """
        if len(alet) == 0:
            return True

        if not isinstance(alet[0], str):
            print_error(f"invalid action primitive {alet[0]}")
            return False

        if alet[0] not in self.behaviour_keywords:
            print_error(f"unknown action primitive {alet[0]}")
            return False

        valid = False

        for chktype in self.behaviour_keywords[alet[0]]:
            if isinstance(alet[1], chktype):
                if chktype == list:
                    valid = (
                        True
                        if (len(alet[1]) % 2 == 0)
                        else isinstance(alet[1][0], dict)
                    )
                elif chktype == dict:
                    s_valid = True
                    for k, v in alet[1].items():
                        if k.endswith("_action"):
                            if (
                                not isinstance(v, list)
                                or len(v) % 2 != 0
                                or not self.validate_action_let(v)
                            ):
                                s_valid = False
                                print_error(
                                    f"action primitive {alet[0]} invalid dict arg {self.behaviour_keywords[alet[0]]}"
                                )
                    valid = s_valid
                else:
                    valid = True
                break

        if not valid:
            print_error(
                f"action primitive {alet[0]} must have arg type of {self.behaviour_keywords[alet[0]]}"
            )

        if len(alet) > 2:
            valid &= self.validate_action_let(alet[2:])

        return valid

    def extract_variables_from_default(self, data):
        """
        Extracts program variables from the default '__init__' behaviour.

        Args:
            data (dict): The loaded behaviour data.
        """
        if data["default"] != "__init__":
            return
        try:
            if data["behaviours"][0]["name"] != "__init__":
                return
            init_action = data["behaviours"][0]["actions"][0]
            if init_action[0][0] == "knowledge":
                self.program_variables.update(init_action[0][1])
                if len(init_action) == 1:  # the file has no default behaviour
                    del data["behaviours"][0]  # delete the __init__ block
        except Exception as _:
            print_error(f"unexpected default init behaviour, ignore")
            return

    def save_master_data(self):
        """
        Saves the composed master behaviour data to the output file.

        Returns:
            bool: True if the data is saved successfully, False otherwise.
        """
        try:
            f = open(self.outputname, "w", encoding="utf-8")
            json.dump(
                self.master_data, f, sort_keys=True, indent=2, separators=(",", ": ")
            )
            f.close()
        except Exception as err:
            print_error(f"unable to save behaviours file {self.outputname}: {err}.")
            return False

        if not os.path.isfile(self.outputname):
            print_error(f"behaviours file {self.outputname} does not exist.")
            return False

        try:
            with open(self.outputname, "r", encoding="utf-8") as f:
                content = f.read()
            content = content.replace("_new_line_", "  \\n")
            if self.asset_url:
                content = content.replace("{BASE_URL}", self.asset_url)
            with open(self.outputname, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as err:
            print_error(
                f"unable to update asset url in behaviours file {self.outputname}: {err}."
            )
            return False

        print(f"saved all validated behaviours into {self.outputname}.")
        return True

    def valid_user_input(self, input, default_yes=True):
        """
        Validates user input for yes/no questions.

        Args:
            input (str): The user's input.
            default_yes (bool): If True, an empty input is considered 'yes'.

        Returns:
            bool: True if the input is considered 'yes', False otherwise.
        """
        if input == "y" or input == "Y":
            return True
        elif input == "":
            return default_yes
        else:
            return False

    def send_to_host(self, upload_image=False):
        """
        Placeholder for sending data to a host, potentially with image upload.

        Args:
            uploadImage (bool): If True, indicates that images should be uploaded.
        """
        pass


if __name__ == "__main__":
    parse = argparse.ArgumentParser(
        description="Compose a master behaviour file from a directory of small json files."
    )
    parse.add_argument(
        "--syntax-check",
        action="store_true",
        help="do ONLY synax check on behaviour file.",
    )
    parse.add_argument(
        "--default-behaviour",
        nargs=1,
        help="set the default behaviour for the master file.",
    )
    parse.add_argument("--asset-url", nargs=1, help="set the base url of image assets.")
    parse.add_argument("--behaviour-output", nargs=1, help="set output file name")
    parse.add_argument(
        "--image-upload",
        nargs="?",
        default="__default__",
        help="set the directory where the images will be uploaded",
    )
    parse.add_argument("datadir", help="json data directory.")
    args = parse.parse_args()

    bcObj = BehaviourComposer()

    if args.default_behaviour:
        bcObj.set_default_behaviour(args.default_behaviour[0])

    if args.behaviour_output:
        bcObj.set_output_name(args.behaviour_output[0])

    if args.asset_url:
        bcObj.set_asset_url(args.asset_url[0])

    if bcObj.load_data_from_directory(args.datadir):
        if args.syntax_check:
            if bcObj.valid_user_input(
                input(
                    f"All behaviour files under {args.datadir} has been validated successfully.\nDo you want to generate the master file? [y/N] "
                ),
                False,
            ):
                bcObj.save_master_data()
        else:
            bcObj.save_master_data()
        exit(0)
    else:
        exit(1)
