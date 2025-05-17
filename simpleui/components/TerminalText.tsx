import styled from "styled-components";
import {pulse} from "./KeyFrames";
import remarkMath from "remark-math";
import rehypeKatex from 'rehype-katex';
import ReactMarkdown from 'react-markdown';
import {Prism as SyntaxHighlighter} from "react-syntax-highlighter";
import { atomDark } from "react-syntax-highlighter/dist/cjs/styles/prism";

import "katex/dist/katex.min.css";

const ContentWithBlinkingCursor = styled.div`
    p:last-of-type::after {
        position: relative;
        top: 3px;
        content: "";
        width: 10px;
        height: 18px;
        background: #1c1406;
        display: inline-block;
        animation: ${pulse} 1.5s steps(2) infinite;
    }
      
    p {
        margin-left: 7px;
        margin-bottom: -2px;
        white-space: pre-line
    }
`;

const NormalContent = styled.div`      
    p {
        margin-left: 7px;
        margin-bottom: -2px;
        white-space: pre-line
    }
`;

function escapeBrackets(text: string): string {
    const pattern = /(```[\S\s]*?```|`.*?`)|\\\[([\S\s]*?[^\\])\\]|\\\((.*?)\\\)/g;
    return text.replace(
      pattern,
      (
        match: string,
        codeBlock: string | undefined,
        squareBracket: string | undefined,
        roundBracket: string | undefined,
      ): string => {
        if (codeBlock != null) {
          return codeBlock;
        } else if (squareBracket != null) {
          return `$$${squareBracket}$$`;
        } else if (roundBracket != null) {
          return `$${roundBracket}$`;
        }
        return match;
      },
    );
  }
  
function escapeMhchem(text: string) {
    return text.replaceAll('$\\ce{', '$\\\\ce{').replaceAll('$\\pu{', '$\\\\pu{');
}

/**
 * Preprocesses LaTeX content by replacing delimiters and escaping certain characters.
 *
 * @param content The input string containing LaTeX expressions.
 * @returns The processed string with replaced delimiters and escaped characters.
 */
function preprocessLaTeX(content: string): string {
    // Step 1: Protect code blocks
    const codeBlocks: string[] = [];
    content = content.replace(/(```[\s\S]*?```|`[^`\n]+`)/g, (match, code) => {
      codeBlocks.push(code);
      return `<<CODE_BLOCK_${codeBlocks.length - 1}>>`;
    });
  
    // Step 2: Protect existing LaTeX expressions
    const latexExpressions: string[] = [];
    content = content.replace(/(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\(.*?\\\))/g, (match) => {
      latexExpressions.push(match);
      return `<<LATEX_${latexExpressions.length - 1}>>`;
    });
  
    // Step 3: Escape dollar signs that are likely currency indicators
    content = content.replace(/\$(?=\d)/g, '\\$');
  
    // Step 4: Restore LaTeX expressions
    content = content.replace(/<<LATEX_(\d+)>>/g, (_, index) => latexExpressions[parseInt(index)]);
  
    // Step 5: Restore code blocks
    content = content.replace(/<<CODE_BLOCK_(\d+)>>/g, (_, index) => codeBlocks[parseInt(index)]);
  
    // Step 6: Apply additional escaping functions
    content = escapeBrackets(content);
    content = escapeMhchem(content);
  
    return content;
}

const TerminalText = ({content, active}) => {
    if (content.includes("\[")) {
        content = preprocessLaTeX(content);
    }
    return ( active ? 
        <ContentWithBlinkingCursor>
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                    code(props) {
                      const {children, className, node, ...rest} = props
                      const match = /language-(\w+)/.exec(className || '')
                      return match ? (
                        <SyntaxHighlighter
                          {...rest}
                          PreTag="div"
                          children={String(children).replace(/\n$/, '')}
                          language={match[1]}
                          style={atomDark}
                        />
                      ) : (
                        <code {...rest} className={className}>
                          {children}
                        </code>
                      )
                    }
                  }}>{content}</ReactMarkdown>
        </ContentWithBlinkingCursor>
        :
        <NormalContent>
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                    code(props) {
                      const {children, className, node, ...rest} = props
                      const match = /language-(\w+)/.exec(className || '')
                      return match ? (
                        <SyntaxHighlighter
                          {...rest}
                          PreTag="div"
                          children={String(children).replace(/\n$/, '')}
                          language={match[1]}
                          style={atomDark}
                        />
                      ) : (
                        <code {...rest} className={className}>
                          {children}
                        </code>
                      )
                    }
                  }}>{content}</ReactMarkdown>
        </NormalContent>
    )
}
export default TerminalText;