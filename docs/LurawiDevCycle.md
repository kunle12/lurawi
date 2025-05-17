# Advanced: End-to-end Lurawi Development

Once you are familiarised with the following topics:
* [Advanced: Running Lurawi as a Dev Container in VS Code](LurawiDevContainer.md). 
* [Advanced: How to Create Lurawi Custom Action Primitives](LurawiCreateCustom.md).

We can now connect all steps together to create an end-to-end development process. In this document, we start an example project ```lurawi_example``` from scratch[1][2], build the workflow and package everything in a docker image that can be deployed in a cloud service.

**NOTE**

[1] We use MacOS as the local development environment, Windows with WSL should have a similar development experience.

## Step 1. Create project

Start a terminal, create a new directory ```lurawi_example``` under user home directory. Create a ```.devcontainer.json``` file under the ```lurawi_example``` with the following content

```json
{
  "image": "kunle12/lurawi:latest",
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python"]
    }
  },
  "forwardPorts": [3031, 8081],
  "mounts": [
      "source=${localWorkspaceFolder},target=/home/lurawi,type=bind,consistency=cached"
  ],
  "workspaceFolder": "/home/lurawi",
  "remoteEnv": {
    "PATH": "${containerEnv:PATH}:/opt/defaultsite/bin",
    "HOME": "/home/lurawi"
  }
}
```

If you will create new custom function scripts, create a ```custom``` subdirectory under the project directory.

## Step 2. Create dev container and run development environment

Start Visual Studio Code app and open folder ```lurawi_example```. Reopen in container as prompted by VS code. (NOTE: If VS code is taking very long to open dev container, you can close the window and try it again to open the folder in a new VS code window).

Open a new terminal under VS code dev container: set environment variables ```PROJECT_NAME``` and ```PROJECT_ACCESS_KEY``` and run ```lurawi dev```.

Open browser to localhost:3031 as prompted by VS code. You should have two following windows opened on your desktop:

<figure>
    <img src="images/run_service.png"
         alt="run development environment" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 1 Running develop environment.</figcaption>
</figure>

Start building the workflow in the visual editor. We have prepared the workflow [lurawi_example.xml](./lurawi_example.xml) so you can load into the visual editor, replacing the model ```qwen3``` in invoke_llm ActionLet with a working LLM model assigned to the project. Dispatch the workflow to the server, test the workflow by sending the following payload to ```http://localhost:8081/lurawi_example/message``` from a REST API test app.

```json
{
  "uid": "dummyid",
  "name": "dummyname",
  "data" : {
  }
}
```

## Step 3. Package workflow in a Docker container image

Now, download the JSON code from **Code** tab and save it as ```lurawi_example.json```. (Unfortunately), you have to manually copy the file from the download directory to your project directory.

Create a Dockerfile with the following content

```Docker
FROM kunle12/lurawi:latest
# update the next line with your project name
ENV PROJECT_NAME lurawi_example
COPY lurawi_example.json /opt/defaultsite
#If you have knowledge file, uncomment the next line
#COPY lurawi_example_knowledge.json /opt/defaultsite
#if you create additional custom function script for your project, uncomment the next line
#COPY custom /opt/defaultsite/lurawi/custom
# remove "--skip-auth" and "--no-ssl-verify" for production deployment
ENTRYPOINT ["python", "app.py", "--skip-auth", "--no-ssl-verify" ]
```

Now you can build a docker image with

```bash
docker build . -t lurawi_example:latest
```

## Step 4. (optional) Create new custom function
As you may have noticed, the existing workflow calling ```query_knowledgebase``` multiple times in order to extract values for different keys from a dictionary (name defined in ```knowledge_key```). It is possible to create a new custom function to do everything in one go. I leave this as a take-home challenge. Spend some effort working out an appropriate function input interface that a block may present graphically.

### Notes on creating custom function scripts
All custom functions must be in the ```lurawi/custom``` directory in the dev container for development and testing. You can create a new custom function by running ```lurawi custom new function_name``` then modify the file. Don’t forget to uncomment line 12 in your ```Dockerfile```.

### Final project structure

You shall have the following file structure in your project directory (as a complete system)

```
lurawi_example
├── custom                      # your project specific custom function scripts
├── lurawi_example.xml              # Block workflow code in XML
├── lurawi_example.json             # JSON workflow code
├── lurawi_example_knowledge.json   # associated JSON knowledge dictionary
├── .devcontainer.json          # Dev container configuration
├── Dockerfile                  # Docker file for building final docker image
└── README.md                   # Add a readme file
 ```

Finally, [lurawi_example_skeleton.zip](./lurawi_example_skeleton.zip) provides a codebase for this example.
