# Lurawi Rest API Specifications

**Endpoint**: http://{LURAWI_SERVER_URL}/{project}/message  
**Method**: POST  
**Payload**:  

```json
{
  "uid": "client/user id",
  "name": "client name",
  "session_id": "optional client provided session id",
  "data" : {
    "message": "a text prompt message",
    "stream" : "true|false"
  }
}
```

```project``` is the project name set in the environment variable ```PROJECT_NAME```.


```uid``` and ```name``` is a unique client user id and client name that may be used for triggering tailored workflow for individual user/client.

```session_id``` is an optional client provided identifier mainly used to trace multi-turn/activity conversations when we enable conversation logging.

```activity_id``` represents a conversation turn returned by a previous workflow call. Client can include the ```activity_id``` used as the reference to log user feedback from a previous conversation turn (in this case, we expect a feedback string item in data dictionary).

```data``` contains a user defined dictionary that pass to the workflow directly:
* ```message``` contains the user input to be sent to the RAG backend.

## Payload Response (non-streaming)

```json
{
  "status": "success",
  "activity_id": "backend service generated id for feedback reference",
  "response": "response text"
}
```

## Payload Response (streaming)

```json
{
  "status": "success",
  "activity_id": "backend service generated id for feedback reference",
  "stream_endpoint": "an endpoint to call to retrieve stream data"
}
```

**NOTE**: stream_endpoint may contain a base URL that may need to be replaced by your gateway URL.

## Feedback Payload

```json
{
  "uid": "client/user id",
  "name": "client name",
  "activity_id": "activity id provided by previous interaction turn",
  "data" : {
    "feedback": "text string that contains user feedback. maybe a strinfied JSON object"
  }
}
```

## Feedback Payload Response

```json
{
  "status": "success"
}
```

## Example

### Input Payload

```json
{
  "uid": "dummyid",
  "name": "dummyname",
  "data" : {
    "message": "What is the longest river in the world?"
  }
}
```

### Response

```json
{
  "status": "success",
  "activity_id": "f2c0dee6-53f0-4786-af7c-37e428877451",
  "response": "The Nile River is traditionally considered the longest river in the world, stretching about 6,650 kilometers (4,130 miles). It flows north through northeastern Africa into the Mediterranean Sea.\n\nHowever, some recent measurements argue that the Amazon River in South America could be slightly longer, depending on the criteria used and the measurement of its tributaries. The Amazon is about 6,400 to 7,062 kilometers (3,980 to 4,390 miles) long, depending on the source.\nThe debate remains open, but the Nile is still often credited as the longest."
}
```
