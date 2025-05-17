import { keyframes } from 'styled-components';

export const pulse = keyframes`
  0% {
    background-color: white;
  }
  100% {
    background-color: black;
  }
`

export const flipin = keyframes`
  from {
    transform: rotateY(180deg) scale(.25);
    opacity: 0;
  }

  to {
    transform: rotateY(0deg) scale(1);
    opacity: 1;
  }
`

export const fadein = keyframes`
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
`

export const fadeout = keyframes`
  from {
    transform: scale(1);
    opacity: 1;
  }

  to {
    transform: scale(.25);
    opacity: 0;
  }
`
