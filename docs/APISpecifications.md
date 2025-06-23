# Lurawi REST API Specifications

This document outlines the specifications for the Lurawi REST API, detailing the endpoints, request payloads, and response structures for interacting with the Lurawi workflow engine.

## Message Endpoint

The primary endpoint for sending messages and triggering workflows within Lurawi.

*   **Endpoint**: `http://{LURAWI_SERVER_URL}/{project}/message`
*   **Method**: `POST`
*   **Description**: Sends a message to a specified Lurawi project, initiating or continuing a workflow.

### Request Payload

```json
{
  "uid": "client/user id",
  "name": "client name",
  "session_id": "optional client provided session id",
  "data": {
    "message": "a text prompt message",
    "stream": "true|false"
  }
}
```

#### Payload Parameters

*   `project`: (Path Parameter) The name of the project, typically configured via the `PROJECT_NAME` environment variable on the Lurawi server.
*   `uid`: (String) A unique client user ID. This can be used to trigger tailored workflows for individual users or clients.
*   `name`: (String) The client's name, which may also be used for personalized workflow triggering.
*   `session_id`: (String, Optional) A client-provided session identifier. Primarily used for tracing multi-turn conversations when conversation logging is enabled.
*   `data`: (Object) A user-defined dictionary passed directly to the workflow.
    *   `message`: (String) The user's input text prompt to be sent to the RAG (Retrieval Augmented Generation) backend.
    *   `stream`: (Boolean, "true" or "false") Indicates whether the response should be streamed.

### Response Payloads

Lurawi provides different response structures based on whether streaming is requested.

#### Non-Streaming Response

```json
{
  "status": "success",
  "activity_id": "backend service generated id for feedback reference",
  "response": "response text"
}
```

*   `status`: (String) Indicates the success or failure of the request.
*   `activity_id`: (String) A backend service-generated ID that can be used as a reference for submitting feedback on this specific conversation turn.
*   `response`: (String) The complete response text from the workflow.

#### Streaming Response

```json
{
  "status": "success",
  "activity_id": "backend service generated id for feedback reference",
  "stream_endpoint": "an endpoint to call to retrieve stream data"
}
```

*   `status`: (String) Indicates the success or failure of the request.
*   `activity_id`: (String) A backend service-generated ID for feedback reference.
*   `stream_endpoint`: (String) An endpoint URL to call to retrieve the streamed data.
    *   **Note**: The `stream_endpoint` may contain a base URL that needs to be replaced by your API Gateway URL if applicable.

## Feedback Endpoint

This section describes the payload for submitting feedback on previous interactions.

### Feedback Request Payload

```json
{
  "uid": "client/user id",
  "name": "client name",
  "activity_id": "activity id provided by previous interaction turn",
  "data": {
    "feedback": "text string that contains user feedback. maybe a stringified JSON object"
  }
}
```

*   `uid`: (String) The unique client user ID.
*   `name`: (String) The client's name.
*   `activity_id`: (String) The `activity_id` obtained from a previous workflow interaction, used to link feedback to a specific conversation turn.
*   `data`: (Object) A dictionary containing the feedback.
    *   `feedback`: (String) A text string containing user feedback. This can also be a stringified JSON object for structured feedback.

### Feedback Response Payload

```json
{
  "status": "success"
}
```

*   `status`: (String) Indicates the success of the feedback submission.

## Example Workflow Interaction

This example demonstrates a typical message exchange with the Lurawi API.

### Example Input Payload

```json
{
  "uid": "dummyid",
  "name": "dummyname",
  "data": {
    "message": "What is the longest river in the world?"
  }
}
```

### Example Response Payload

```json
{
  "status": "success",
  "activity_id": "f2c0dee6-53f0-4786-af7c-37e428877451",
  "response": "The Nile River is traditionally considered the longest river in the world, stretching about 6,650 kilometers (4,130 miles). It flows north through northeastern Africa into the Mediterranean Sea.\n\nHowever, some recent measurements argue that the Amazon River in South America could be slightly longer, depending on the criteria used and the measurement of its tributaries. The Amazon is about 6,400 to 7,062 kilometers (3,980 to 4,390 miles) long, depending on the source.\nThe debate remains open, but the Nile is still often credited as the longest."
}
```
