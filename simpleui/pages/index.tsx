import styled from "styled-components";
import {FullCentredLayout} from "../components/Layout";

const BackgroundImage = styled.div`
  background-image: url("assets/images/lurawi_logo.png");
  background-position: center;
  background-repeat: no-repeat;
  background-size: contain;
  width: 100%;
  height: 100%;
`;

const Index = () => (
  <FullCentredLayout>
    <BackgroundImage/>
  </FullCentredLayout>
);

export default Index
