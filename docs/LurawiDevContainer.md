# Advanced: Running Lurawi as a Dev Container in VS Code

Advanced customisations of Lurawi can be achieved through mounting the prebuilt Lurawi docker image as a [Dev Container under Visual Studio Code](https://code.visualstudio.com/docs/devcontainers/containers). To do this, you need:

* A recent version of Visual Studio Code (1.5+) installed.
* Dev Container extension module is installed in VS code.
* A recent Docker Desktop installed and running.

## Two Steps

1. create a new project directory, e.g. ```lurawi```, under your home directory. On MacOS: ```/Users/{user_name}/lurawi```
2. Download [devcontainer.json](../.devcontainer.json) and save it in a newly created ```lurawi``` folder as ```.devcontainer.json```. Open the folder in VS code, you will be prompted to reopen as a Dev Container (Fig. 1).

<figure>
    <img src="images/devcontainer1.png"
         alt="Open Lurawi as a Dev Container" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 1 Open Lurawi as a Dev Container.</figcaption>
</figure>

It usually takes a while to download Lurawi docker image and open it in a running container. Once the process is completed, you shall see the entire source code working directory:

<figure>
    <img src="images/devcontainer2.png"
         alt="Lurawi in Dev Container" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 2 Lurawi in Dev Container.</figcaption>
</figure>

In terminal, set the minimum environment variables for your agent project:
```bash
export PROJECT_NAME=project_name
export PROJECT_ACCESS_KEY=project_access_key_provided
```
finally, run
```bash
lurawi dev
```

You will be prompted to open a local browser window to http://localhost:3031. You can proceed with building a workflow.

## Install Additional Python libraries
```bash
pip install ${library_name}
```

**NOTE**: put additional library dependencies in a ```requirements.txt``` file.
