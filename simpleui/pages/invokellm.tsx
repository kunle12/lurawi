import React, { useEffect, useState, useRef } from "react";
import { useRouter } from "next/router";
import {
  Col, Container, Row, Form, Button,
  Spinner, Card, InputGroup,
  Popover, OverlayTrigger, Image, Modal
} from "react-bootstrap";
import { fetchEventSource  } from "fetch-event-source-sse";
import Collapsible from "../components/Collapsible";
import TerminalText from "../components/TerminalText";

class FatalError extends Error { }

interface FormValues {
  prompt: string
  streaming: boolean
  temperature: number
}

interface Popup {
  show: boolean,
  title?: string
  message?: string
  status?: 'success' | 'error'
}

const startThinkToken = "<think>"
const endThinkToken = "</think>"

const LLMPromptForm = () => {
  const router = useRouter();

  const [formData, setFormData] = useState<FormValues>();
  const [validated, setValidated] = useState(false);
  const [llmOutput, setLLMOutput] = useState("")
  const [llmThought, setLLMThought] = useState("")
  const [popup, setPopUp] = useState<Popup>({ show: false, title: "Title Here", message: "This is a message." });
  const [loading, setLoading] = useState<boolean>(false)

  const cachedResponseRef = useRef([]);
  const smoothStreamRef = useRef(false);
  const divRef = useRef(null);

  useEffect(() => {
    divRef.current?.scrollIntoView({ behavior: 'smooth' });
  });
  

  useEffect(() => {
    if (router.isReady) {
      if (typeof process.env.NEXT_PUBLIC_PROJECT === "undefined" ||
          typeof process.env.NEXT_PUBLIC_LURAWI_URL === "undefined" ||
          typeof process.env.NEXT_PUBLIC_PROJECT_ACCESS_KEY === "undefined")
      {
        setPopUp({
          show: true,
          status: "error",
          title: "Uh Oh!",
          message: "Missing environmental variable(s)"
        })
      }
      else {
        try {
          const { smooth } = router.query;
          if (typeof smooth !== 'undefined') {
            smoothStreamRef.current = (smooth === 'true');
          }
        }
        catch {
          console.log('error getting input argument.')
        }
      }
    }
  }, [router.isReady]);

  useEffect(() => {
    let interval = null;
    if (smoothStreamRef.current) {
      console.log('start streaming interval')
      interval = setInterval(() => {
        if (cachedResponseRef.current.length > 0) {
          setLLMOutput((text)=> text + cachedResponseRef.current.shift());
        }
      }, 100)
    }
    return () => { if (interval != null) clearInterval(interval)};
  }, [smoothStreamRef.current]);

  const postSubmission = async (formValues: FormValues) => {
    let start_time = Date.now()
    let stream_time = -1
    setLLMThought("")
    setLoading(true)
    let url = ''
    url = `${process.env.NEXT_PUBLIC_LURAWI_URL}/${process.env.NEXT_PUBLIC_PROJECT}/message`
    const payload_dict = {
      "uid": "dummyid",
      "name": "dummyname",
      "data" : {
        "message": formValues.prompt,
        "stream": true
      }
    }
    let payload = JSON.stringify(payload_dict)
    let headers = {
      'Content-Type': 'application/json',
      'X-LURAWI-API-KEY': process.env.NEXT_PUBLIC_PROJECT_ACCESS_KEY,
      'X-Accel-Buffering': 'no'
    }
    
    const postOptions = {
      method: 'POST',
      headers: headers,
      body: payload
    }

    let accumulated_content = ""

    fetch(url, postOptions)
      .then((response) => response.json())
      .then((result) => {
        if (result['status'] === 'success') {
          if ('stream_endpoint' in result) {
            let stream_url = result['stream_endpoint']
            if ('stream_access_key' in result) {
              headers['X-LURAWI-API-KEY'] = result['stream_access_key']
            }
            fetchEventSource(stream_url, {
              method: 'GET',
              headers: headers,
              credentials: "same-origin",
              onmessage(ev) {
                if (stream_time == -1) {
                  stream_time = Date.now()
                  console.log(`delay to the start stream ${stream_time-start_time}`)
                }
                let content = ev.data.replaceAll('<br/>', '  \n')
                if (content.startsWith(startThinkToken)) {
                  accumulated_content = content = content.slice(8)
                }
                else {
                  accumulated_content += content
                  if (accumulated_content.includes(endThinkToken)) {
                    const [thought, remain] = accumulated_content.split(endThinkToken)
                    setLLMThought(thought.trim())
                    setLLMOutput("")
                    accumulated_content = content = remain.trim()
                  }
                }
                if (smoothStreamRef.current) {
                  cachedResponseRef.current.push(content);
                }
                else {
                  setLLMOutput((text) => text + content);
                }
              },
              onerror(err) {
                if (err instanceof FatalError) {
                    throw err; // rethrow to stop the operation
                } else {
                    // do nothing to automatically retry. You can also
                    // return a specific retry interval here.
                }
                console.log(`streaming error ${err}`)
                return 100
              },
              onclose() {
                console.log(`total streaming time ${Date.now()-stream_time}`)
                setLoading(false)
              }
            })
          }
          else {
              setLLMOutput(result['response'])
              setLoading(false)
          }
        } else {
            setPopUp({
              show: true,
              status: "error",
              title: "Something went wrong!",
              message: result['message']
            })
        }
      }
    ).catch((error) => {
      setLoading(false)
      setPopUp({
        show: true,
        status: "error",
        title: "Something went wrong!",
        message: error.message
      })
    })
  }

  const handleSubmission = async (event) => {
    event.preventDefault();

    setLLMOutput("")
    const form = event.currentTarget;
    const data = new FormData(form);

    if (!form.checkValidity()) {
      event.preventDefault();
      event.stopPropagation();
    } else {
      let formValues: FormValues = {
        prompt: data.get('prompt') as string,
        streaming: true,
        temperature: parseFloat(data.get('temperature') as string)
      };
      await postSubmission(formValues)
    }
    setValidated(true);
  };

  const handlePromptChange = e => setFormData({ ...formData, prompt: e.target.value })

  const handleClose = () => setPopUp({ show: false })
  return (
    <div style={{ backgroundColor: "#F1F7FB", height: '100%', width: '100%', fontFamily: 'Gilroy-Regular' }}>
      <Container style={{ maxWidth: "800px" }}>
          <>
            <Row>
              <Col style={{ textAlign: "center" }}>
                <h1 style={{ margin: '1em 0 1em 0', fontSize: '1.5em', fontFamily: 'Gilroy-SemiBold' }}>Welcome to Lurawi Test Console!</h1>
              </Col>
            </Row>
            <Row style={{ marginBottom: '2em' }}>
              <Col style={{ marginLeft: 'auto', marginRight: 'auto', maxWidth: '800px', marginTop: '1em' }}>
                <Card body style={{
                  border: 'none',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.04), 0 2px 4px rgba(0,0,0,0.04), 0 4px 8px rgba(0,0,0,0.04), 0 8px 16px rgba(0,0,0,0.04),0 16px 32px rgba(0,0,0,0.04), 0 32px 64px rgba(0,0,0,0.04)'
                }}>
                <Row style={{ marginBottom: '0.8em' }} >
                  <Form.Group as={Col}>
                    <Form.Label style={{ fontWeight: 'bold' }}> 🖨 Output from Agent</Form.Label>
                  </Form.Group>
                  <Container style={{ height: "400px", maxHeight: "400px", overflowY: "auto"}}>
                    {
                      llmThought ?
                      <Collapsible title="Think" content={llmThought}/> : null
                    }
                    <TerminalText content={llmOutput} active={cachedResponseRef.current.length > 0 || loading}/>
                    <div ref={divRef} />
                  </Container>
                </Row>
                  <Form noValidate validated={validated} onSubmit={handleSubmission}>
                    <Row style={{ marginBottom: '0.8em' }} >
                      <Form.Group as={Col}>
                        <Form.Label style={{ fontWeight: 'bold' }} > ⌨ Enter your message</Form.Label>
                        <Form.Control
                          name="prompt"
                          required
                          type="text"
                          placeholder="Please enter your text here"
                          defaultValue=""
                          onChange={handlePromptChange}
                          onFocus={e => e.target.select()}
                        />
                      </Form.Group>
                    </Row>
                    <Row style={{ marginBottom: '0.8em' }}>
                      <Button style={{ marginLeft: 'auto', marginRight: 'auto', maxWidth: '140px', marginTop: '0.8em' }} type="submit">
                        {(loading || cachedResponseRef.current.length > 0) ? <Spinner style={{ width: '20px', height: '20px' }} animation="border" role="status" /> : 'Submit'}
                      </Button>
                    </Row>
                  </Form>
                </Card>
              </Col>
            </Row>
          </>

        <Modal centered show={popup.show} onHide={handleClose}>
          <Modal.Header closeButton>
            <Modal.Title>{popup.title}</Modal.Title>
          </Modal.Header>
          <Modal.Body>{popup.message}</Modal.Body>
        </Modal>
      </Container>
    </div>
  )
}

export default LLMPromptForm
