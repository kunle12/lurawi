# Advanced: Lurawi CLI

## Prerequisite

* Run [Lurawi as a dev docker container](LurawiDevContainer.md).
* Set environment variables: ```PROJECT_NAME``` and ```PROJECT_ACCESS_KEY```

## CLI Commands

Open a terminal in VS Code and run ```lurawi -h``` as shown in Fig. 1.

<figure>
    <img src="images/lurawicli.png"
         alt="Lurawi CLI" width="300px"
         />
    <figcaption>Fig. 1 lurawi cli running in dev container terminal.</figcaption>
</figure>

### Available functions

|Command|Description|
|----|------------|
|```lurawi version```|Show current Lurawi version.|
|```lurawi run```|Run Lurawi service.|
|```lurawi dev```|Run Lurawi development environment: this starts visual editor.|
|```lurawi create project_name```|Create a new Lurawi project XML file from default template. The XML file can be opened in the visual editor.|
|```lurawi custom list```|List all available Lurawi Custom functions.|
|```lurawi custom new custom_name```|Create a new custom function from default template. Edit the Python code in VS code.|
 