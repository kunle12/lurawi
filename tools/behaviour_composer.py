#! /usr/bin/env python3
from __future__ import print_function
import os
import sys
import argparse
import simplejson as json


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class BehaviourComposer(object):
    def __init__(self):
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
        self.master_data["default"] = name

    def set_output_name(self, name):
        self.outputname = name

    def set_asset_url(self, url):
        self.asset_url = url

    def load_data_from_directory(self, path):
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
        data = None
        valid = True
        if script is not None:
            try:
                f = open(script, "r")
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
                self.extractVariablesFromDefault(data)
            for be in data["behaviours"]:
                if "actions" not in be:
                    print_error(f"missing actions in behaviour {be['name']}")
                    valid = False
                    break
                for id_ac, ac in enumerate(be["actions"]):
                    for id_al, al in enumerate(ac):
                        if isinstance(al, list):
                            if len(al) % 2 != 0 or not self.validateActionLet(al):
                                valid = False
                                print_error(
                                    f"invalid actionlet in behaviour {be['name']} action {id_ac} index {id_al}."
                                )
                        else:
                            valid = False
                            print_error(
                                f"invalid behaviour {be['name']} action {id_ac} {al}."
                            )
        except:
            print_error("the behaviour file contains unresolved errors.")
            valid = False

        if valid:
            return (default_demo, data["behaviours"])
        else:
            print_error(f"loaded behaviour file {script} is corrupted.")
            return (None, None)

    def validateActionLet(self, alet):
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
                                or not self.validateActionLet(v)
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
            valid &= self.validateActionLet(alet[2:])

        return valid

    def extractVariablesFromDefault(self, data):
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
        except:
            print_error(f"unexpected default init behaviour, ignore")
            return

    def saveMasterData(self):
        try:
            f = open(self.outputname, "w")
            json.dump(
                self.master_data, f, sort_keys=True, indent=2, separators=(",", ": ")
            )
            f.close()
        except:
            print_error(f"unable to save behaviours file {self.outputname}.")
            return False

        if not os.path.isfile(self.outputname):
            print_error(f"behaviours file {self.outputname} does not exist.")
            return False

        try:
            with open(self.outputname, "r") as f:
                content = f.read()
            content = content.replace("_new_line_", "  \\n")
            if self.asset_url:
                content = content.replace("{BASE_URL}", self.asset_url)
            with open(self.outputname, "w") as f:
                f.write(content)
        except:
            print_error(
                f"unable to update asset url in behaviours file {self.outputname}."
            )
            return False

        print(f"saved all validated behaviours into {self.outputname}.")
        return True

    def validUserInput(self, input, default_yes=True):
        if input == "y" or input == "Y":
            return True
        elif input == "":
            return default_yes
        else:
            return False

    def sendToHost(self, uploadImage=False):
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
        bcObj.set_asset_uRL(args.asset_url[0])

    if bcObj.load_data_from_directory(args.datadir):
        if args.syntax_check:
            if bcObj.validUserInput(
                input(
                    "All behaviour files under {} has been validated successfully.\nDo you want to generate the master file? [y/N] ".format(
                        args.datadir
                    )
                ),
                False,
            ):
                bcObj.saveMasterData()
        else:
            bcObj.saveMasterData()
        exit(0)
    else:
        exit(1)
