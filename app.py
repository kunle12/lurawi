#!/usr/bin/env python3

import os
import sys
import argparse
import uvicorn
from lurawi import utils

from lurawi.workflow_service import WorkflowService

DEFAULT_BEHAVIOUR_SCRIPT = "lurawi_example"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-auth", action="store_false", help="Skip authentication step."
    )
    parser.add_argument(
        "--no-ssl-verify",
        action="store_true",
        help="Skip SSL certificate verifications.",
    )
    parser.add_argument("--dev", action="store_false", help="Enable development mode")
    args = parser.parse_args()

    utils.no_auth = not args.skip_auth
    utils.ssl_verify = not args.no_ssl_verify
    utils.in_dev = not args.dev

    if not utils.get_project_settings():
        sys.exit(-1)

    behaviour_script = (
        DEFAULT_BEHAVIOUR_SCRIPT
        if utils.project_name == "lurawi"
        else utils.project_name
    )
    server = WorkflowService(behaviour_script)
    app = server.create_app()

    try:
        uvicorn.run(
            app, host=os.getenv("HOST", "localhost"), port=int(os.getenv("PORT", "8081"))
        )
    except KeyboardInterrupt:
        pass
