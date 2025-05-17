import React, { useState } from 'react';
import styled from "styled-components";

const CollaspsibleContent = styled.div`
    h2 {
        font-size: 1.3em;
        font-weight: bold;
    }

    button {
        background-color: transparent;
        background-repeat: no-repeat;
        border: none;
        cursor: pointer;
        overflow: hidden;
        outline: none;    
    }
    div {
        margin-left: 10px;
        width: 95%;
    }
    table, th, td {
        border: 2px solid;
        border-color: #DEE2E6;
        border-radius: 10px;
    }

    p {
        margin-left: 7px;
        margin-bottom: -2px;
    }
`;

const Collapsible = ({title, content}) => {
    const onClick = () => {
        setIsOpen((prev) => !prev)
    }
    const [isOpen, setIsOpen] = useState<Boolean>(true)

    let expandButton = null
    if (isOpen) {
        expandButton = <button onClick={onClick}> &#9660; {title} </button>
    }
    else {
        expandButton = <button onClick={onClick}> &#9654; {title} </button>
    }

    // special hack to process corrupted html chunk
    if (content.startsWith('</p>')) {
        content = content.slice(4)
    }
    if (content.endsWith('<p>')) {
        content = content.slice(0,-3)
    }
    const html_content = (<div dangerouslySetInnerHTML={{ __html: content}} />)
    return (
        <CollaspsibleContent>
            {expandButton}
            {isOpen ? html_content : null }
        </CollaspsibleContent>
    )
}
export default Collapsible;