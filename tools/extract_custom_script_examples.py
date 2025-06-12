#! /usr/bin/env python3
"""
This module extracts example information from custom Python script class docstrings
to construct an XML definition file for the Lurawi Visual Programming system.
It parses Python files, looks for class docstrings containing a specific '"custom"'
marker, and then extracts argument definitions to generate XML tags.
"""

from __future__ import print_function
import os
import argparse
import ast


def parse_custom_scripts(fdir):
    """
    Parses all custom Python scripts in a given directory and its subdirectories
    to extract example information.

    Args:
        fdir (str): The path to the directory containing custom scripts.

    Returns:
        str: A concatenated string of XML content extracted from the scripts.
    """
    content = ""
    for root, _, files in os.walk(fdir, topdown=False):
        for name in files:
            if name.endswith(".py") and name != "__init__.py":
                print(f"processing custom script {name}")
                content = content + extract_example_info(os.path.join(root, name))
    return content


def extract_example_info(fname):
    """
    Extracts example information from the docstring of a single Python file.
    It specifically looks for class docstrings that contain a '"custom"' marker
    and then parses a JSON-like structure within to get script name and arguments.

    Args:
        fname (str): The path to the Python file.

    Returns:
        str: An XML string representing the custom script definition, or an empty string
             if no valid example is found or an error occurs.
    """
    content = ""
    with open(fname, "r", encoding="UTF-8") as f:
        tree = ast.parse(f.read())

        modef = tuple({ast.ClassDef: "Class"})
        for n in ast.walk(tree):
            if isinstance(n, modef):
                ds = ast.get_docstring(n)
                # print("extracted class docstring {}".format(ds))
                if ds is None:
                    continue
                cindex = ds.find('"custom"')
                if cindex > 0:
                    exstr = ds[ds.rfind("[", 0, cindex) :]
                    eindex = exstr.rfind("]", 0, len(exstr))
                    if eindex <= 0:
                        print(f"unable to parse doc string example 1: {exstr}")
                        continue
                    exstr = exstr[: eindex + 1]
                    try:
                        exalet = ast.literal_eval(exstr)
                    except Exception as err:
                        print(
                            f"unable to parse doc string example 2: {exstr} error {err}"
                        )
                        continue

                    if not isinstance(exalet, list) or len(exalet) != 2:
                        print(f"unable to parse the example 3: {exalet}")
                        continue
                    if isinstance(exalet[1], dict):
                        # print("custom script {} with".format(exalet[1]['name']))
                        content = (
                            content + f"\t<cscript name=\"{exalet[1]['name']}\">\n"
                        )
                        kargs = exalet[1]["args"]
                        for k, t in kargs.items():
                            atype = "any"
                            if isinstance(t, bool):
                                atype = "boolean"
                            elif isinstance(t, str):
                                atype = "string"
                            elif isinstance(t, float) or isinstance(t, int):
                                atype = "number"
                            elif isinstance(t, list) and (
                                "action" in k or "command" in k
                            ):
                                atype = "action"
                            content = (
                                content
                                + f'\t\t<argument type="{atype}">{k}</argument>\n'
                            )
                        content = content + "\t</cscript>\n"
                    elif isinstance(exalet[1], str):
                        # print("custom script: {} no arg".format(exalet[1]))
                        content = (
                            content + f'\t<cscript name="{exalet[1]}"></cscript>\n'
                        )
                    else:
                        print(f"unable to parse doc string example 4: {exstr}")
                        continue
                else:
                    continue
    return content


if __name__ == "__main__":
    parse = argparse.ArgumentParser(
        description="Extract example from custom script class docstring to construct a XML definition file for Lurawi Visual Programming system"
    )
    parse.add_argument("--output", nargs=1, help="set output file name")
    parse.add_argument("datadir", help="custom script directory.")
    args = parse.parse_args()

    outputname = "custscript_def.xml"
    if args.output:
        outputname = args.output[0]

    content = parse_custom_scripts(args.datadir)
    if content != "":
        try:
            with open(outputname, "w", encoding='utf-8') as file:
                file.write(
                    '<xml xmlns="http://www.w3.org/1999/xhtml" id="scriptlib" style="display: none;">\n'
                )
                file.write(content)
                file.write("</xml>\n")
                file.close()
        except Exception as _:
            print(f"unable to save custom script definition to {outputname}.")
        print(f"saved custom script definition to {outputname}")
