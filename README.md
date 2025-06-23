# Lurawi - An Agent Workflow Orchestration Engine

## Table of Contents
- [Introduction](#introduction)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Pulling the Lurawi Docker Image](#pulling-the-lurawi-docker-image)
  - [Launching the Lurawi Docker Container](#launching-the-lurawi-docker-container)
- [Working with the Lurawi Agent Workflow Visual Editor](#working-with-the-lurawi-agent-workflow-visual-editor)
  - [Loading an Example Workflow](#loading-an-example-workflow)
  - [Dispatching the Workflow](#dispatching-the-workflow)
  - [Viewing Generated Code](#viewing-generated-code)
- [Testing the Workflow](#testing-the-workflow)
- [Saving the Workflow](#saving-the-workflow)
- [Next Steps](#next-steps)
- [Notes](#notes)

## Introduction

Lurawi is a NoCode/LowCode development environment designed for building sophisticated agent-based workflows. It empowers Machine Learning (ML) and Generative AI (GenAI) engineers to interactively design, experiment with, and implement complex workflows with minimal effort. The output of this process is an XML/JSON-based data file, ready for deployment and execution on the Lurawi runtime engine within a container image. This containerized solution can be seamlessly deployed in cloud environments such as AWS.

## Key Features

*   **Visual Workflow Design:** Compose workflows intuitively using a drag-and-drop interface on a canvas.
*   **Minimal Coding:** Leverage visual construction to build workflows, significantly reducing the need for traditional programming.
*   **Modular and Extensible Architecture:** Extend system capabilities by encapsulating functionalities within modular custom function classes.
*   **Unified REST API Specification:** Access a comprehensive, out-of-the-box REST API. Refer to the [API Specifications](./docs/APISpecifications.md) for details.
*   **Cloud-Ready Deployment:** Easily deploy workflows as Docker containers in environments like AWS.
*   **Lurawi-in-a-Box:** A self-contained Docker image providing a fully functional Lurawi system for local execution, requiring only Docker Desktop.

The following sections provide detailed instructions on how to experiment with Lurawi using the prebuilt Docker image.

## Quick Start

For a rapid setup and initial exploration, execute the following Docker command. Ensure you replace `{YOUR_PROJECT_NAME}` and `{YOUR_ACCESS_KEY}` with your registered project details.

```bash
docker run -d \
  -p 3031:3031 \
  -p 8081:8081 \
  -e PROJECT_NAME={YOUR_PROJECT_NAME} \
  -e PROJECT_ACCESS_KEY={YOUR_ACCESS_KEY} \
  kunle12/lurawi:latest
```

## Installation

**NOTE:** For advanced setup, including a VS Code Development Container configuration, please refer to [Lurawi setup as VS Code Dev Container](./docs/LurawiDevContainer.md).

### Prerequisites

Ensure your workstation supports virtualization and has [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed.

### Pulling the Lurawi Docker Image

To obtain the latest Lurawi Docker image, execute the following command:

```bash
docker pull kunle12/lurawi:latest
```

Upon successful download, the `kunle12/lurawi:latest` image will be available in your Docker Desktop environment.

<figure>
    <img src="docs/images/lurawi_in_docker_1.png"
         alt="Lurawi image in docker">
    <figcaption>Fig. 1 Downloaded Lurawi Docker image under Docker Desktop.</figcaption>
</figure>

### Launching the Lurawi Docker Container

To launch the Lurawi container, you can use the Docker Desktop UI by clicking the "Play" button under "Actions" for the `kunle12/lurawi:latest` image.

Alternatively, for more control and reproducibility, use the following command in your terminal:

```bash
docker run -d \
  -p 3031:3031 \
  -p 8081:8081 \
  -e PROJECT_NAME={YOUR_PROJECT_NAME} \
  -e PROJECT_ACCESS_KEY={YOUR_ACCESS_KEY} \
  kunle12/lurawi:latest
```

**Important:**
*   Bind your local machine ports `3031` and `8081` to the container's respective ports.
*   Set the `PROJECT_NAME` and `PROJECT_ACCESS_KEY` environment variables to your registered project name and access key.

After launching, you should observe container logs in Docker Desktop similar to the example below, indicating a successful startup:

<figure>
    <img src="docs/images/lurawi_in_docker_3.png"
         alt="Launched Lurawi container in docker" width="500px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 2 Launch of Lurawi Docker container.</figcaption>
</figure>

## Working with the Lurawi Agent Workflow Visual Editor

Open your preferred web browser and navigate to `http://localhost:3031` to access the Lurawi Agent Workflow Visual Editor:

<figure>
    <img src="docs/images/lurawi_desktop.png"
         alt="Lurawi Visual Editor" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 3 Lurawi agent workflow visual editor.</figcaption>
</figure>

### Loading an Example Workflow

Download the example workflow file: [lurawi_example.xml](./lurawi_example.xml).

In the visual editor, click the <img src="https://user-images.githubusercontent.com/6646691/100293076-9e48a580-2fd6-11eb-8423-44074da2b4e6.png" width="20" style="vertical-align:middle;"/> button to load this file. The editor will then display the example workflow. Remember to update the model name (highlighted in red in Fig. 4) to a model assigned to your project.

<figure>
    <img src="docs/images/lurawi_load_file.png"
         alt="Workflow in Lurawi Visual Editor" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 4 Loaded example workflow.</figcaption>
</figure>

### Dispatching the Workflow

To dispatch the current workflow to the Lurawi runtime server (running in the Docker container) for testing, click the <img src="docs/images/dispatch_icon.png" width="22" style="vertical-align:middle;"/> button.

<figure>
    <img src="docs/images/lurawi_upload.png"
         alt="Dispatch Workflow to runtime engine" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 5 Successfully uploaded the workflow to the Lurawi runtime engine.</figcaption>
</figure>

### Viewing Generated Code

Navigate to the **Code** tab (Fig. 6) to view the JSON-based code dynamically generated from the visual blocks in the **Blocks** tab. The visual blocks serve as the source code, while the JSON code represents the compiled, executable program. If the visual block program contains errors, the **Code** tab will display error messages instead of valid JSON. In such cases, switch back to the **Blocks** tab to rectify the errors, then return to the **Code** tab for validation.

<figure>
    <img src="docs/images/lurawi_code_json.png"
         alt="Code tab showing JSON output" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 6 Code tab (circled in red) showing the JSON code generated from the visual program blocks.</figcaption>
</figure>

## Testing the Workflow

Click the <img src="docs/images/console_icon.png" width="20" style="vertical-align:middle;"/> button to open a new tab to the Lurawi test console (Fig. 7) and begin interacting with your workflow by typing questions or messages.

<figure>
    <img src="docs/images/lurawi_test_console.png"
         alt="Lurawi Test Console" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 7 Lurawi Test Console.</figcaption>
</figure>

**Note on Test Console Payload:**  
This test console is specifically designed for the following input payload structure:

```json
{
  "uid": "client/user id",
  "name": "client name",
  "session_id": "optional client provided session id",
  "data" : {
    "message": "a text prompt message"
  }
}
```

If you modify the `data` payload structure within your workflow, the test console may no longer function as expected. For workflows with custom data structures, use `curl` or other REST API testing tools to call the endpoint at `http://localhost:8081/projects/{your_project_name}/message`.

## Saving the Workflow

Click the <img src="https://user-images.githubusercontent.com/6646691/100292760-8886b080-2fd5-11eb-919a-1e2aad62ee17.png" width="20" style="vertical-align:middle;"/> button to download the finalized workflow from the visual editor. You can download two files: an XML file from the **Blocks** tab (containing the visual block code) and a JSON program code file from the **Code** tab (used by Lurawi for execution).

<figure>
    <img src="docs/images/lurawi_saving_workflow.png"
         alt="Saving Workflow" width="600px"
         style="display: block; margin: 0 auto"/>
    <figcaption>Fig. 8 Saving visual block code in Blocks tab.</figcaption>
</figure>

It is recommended to save both files in a version-controlled repository, such as GitHub. With a properly configured CI/CD pipeline (e.g., GitHub Actions), a custom Docker image can be automatically built and deployed to production environments.

## Next Steps

The Lurawi agent workflow visual editor is built upon [Google Blockly](https://developers.google.com/blockly). If you are new to block-based coding, it is highly recommended to familiarize yourself with its mechanics through tutorials, such as those provided by [Scratch](https://scratch.mit.edu/).

Once comfortable with block-based programming, delve into:
*   [Lurawi Specific Block Concepts](./docs/LurawiConcepts.md) for an understanding of core Lurawi block principles.
*   [Lurawi Prebuilt Custom Blocks](./docs/LurawiGenAiCustoms.md) for detailed descriptions of prebuilt custom function blocks.
*   [Advanced: RAG Reference Implementation in Lurawi](./docs/RAGReferenceImplementation.md) for a concrete example of a Retrieval-Augmented Generation (RAG) implementation.

Lurawi's capabilities are extensible via a plug-in mechanism, allowing integration with third-party systems. Explore [Advanced: How to Create Lurawi Custom Action Primitives](./docs/LurawiGenAiCustoms.md) to learn more.

Finally, review the [Advanced: End-to-end Lurawi Development](./docs/LurawiDevCycle.md) example for a comprehensive development cycle overview.

### Notes

1.  **Lurawi Code Repository:** [https://github.com/kunle12/lurawi](https://github.com/kunle12/lurawi)
