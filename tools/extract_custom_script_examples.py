#! /usr/bin/env python3
"""
This module extracts example information from custom Python script class docstrings
to construct an XML definition file for the Lurawi Visual Programming system.
It parses Python files, looks for class docstrings containing a specific '"custom"'
marker, and then extracts argument definitions to generate XML tags.
"""

import argparse
import ast
import os


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


def _infer_type(t, k):
    """Infer the argument type from its example value and key name."""
    if isinstance(t, bool):
        return "boolean"
    if isinstance(t, str):
        return "string"
    if isinstance(t, float) or isinstance(t, int):
        return "number"
    if isinstance(t, list) and ("action" in k or "command" in k):
        return "action"
    return "any"


def _merge_args(examples):
    """Merge argument definitions from multiple examples into one.

    For each key, if all examples agree on the type use that; otherwise 'any'.
    Returns a list of (key, type) pairs with success_action and failed_action last.
    """
    merged = {}
    for ex in examples:
        args = ex.get("args", {})
        for k, v in args.items():
            atype = _infer_type(v, k)
            if k not in merged:
                merged[k] = set()
            merged[k].add(atype)

    result = []
    tail = []
    for k, types in merged.items():
        atype = "any" if len(types) != 1 else next(iter(types))
        if k in ("success_action", "failed_action"):
            tail.append((k, atype))
        else:
            result.append((k, atype))
    return result + tail


def _extract_examples(ds):
    """Extract all ['custom', ...] examples from a docstring."""
    examples = []
    pos = 0
    while True:
        cindex = ds.find('"custom"', pos)
        if cindex < 0:
            break

        # Search backward from "custom" for the '[' that starts this expression.
        # Only accept a '[' that is on the same line to avoid unrelated brackets.
        bracket_pos = -1
        for i in range(cindex, 0, -1):
            if ds[i] == "[" and ds[i:cindex].find("\n") < 0:
                bracket_pos = i
                break
        if bracket_pos < 0:
            pos = cindex + 1
            continue

        # Proper bracket matching: find the matching ']'
        depth = 0
        eindex = -1
        for i in range(bracket_pos, len(ds)):
            ch = ds[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    eindex = i
                    break
        if eindex <= bracket_pos:
            pos = cindex + 1
            continue

        exstr = ds[bracket_pos : eindex + 1]
        try:
            exalet = ast.literal_eval(exstr)
        except Exception:
            pos = cindex + 1
            continue
        if not isinstance(exalet, list) or len(exalet) != 2:
            pos = cindex + 1
            continue
        if isinstance(exalet[1], dict):
            examples.append(exalet[1])
        elif isinstance(exalet[1], str):
            examples.append({"name": exalet[1], "args": {}})
        pos = eindex + 1
    return examples


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
    with open(fname, encoding="UTF-8") as f:
        tree = ast.parse(f.read())

        modef = (ast.ClassDef,)
        for n in ast.walk(tree):
            if isinstance(n, modef):
                ds = ast.get_docstring(n)
                if ds is None:
                    continue
                examples = _extract_examples(ds)
                if not examples:
                    continue

                # Group examples by script name
                by_name = {}
                for ex in examples:
                    ename = ex.get("name", "")
                    if ename:
                        by_name.setdefault(ename, []).append(ex)

                for sname, exs in by_name.items():
                    merged = _merge_args(exs)
                    content += f'\t<cscript name="{sname}">\n'
                    for k, atype in merged:
                        content += f'\t\t<argument type="{atype}">{k}</argument>\n'
                    content += "\t</cscript>\n"
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
            with open(outputname, "w", encoding="utf-8") as file:
                file.write(
                    '<xml xmlns="http://www.w3.org/1999/xhtml" id="scriptlib" style="display: none;">\n'
                )
                file.write(content)
                file.write("</xml>\n")
                file.close()
        except Exception as _:
            print(f"unable to save custom script definition to {outputname}.")
        print(f"saved custom script definition to {outputname}")
