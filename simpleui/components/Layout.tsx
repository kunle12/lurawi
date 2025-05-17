import styled from "styled-components";

const FullCentredLayout = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  height: 100%;
  text-align: center;
`;

const BackgroundImage = styled.div`
  background-image: url(${props => props.theme.image || "../assets/images/image-missing.png"});
  background-position: center;
  background-repeat: no-repeat;
  background-size: contain;
  width: 100%;
  height: 100%;
`;

const Content = styled.div`
  padding: 2rem;
  justify-content: center;
  text-align: center;
  height: 100%;
  width:100%;
  color: #F1F7FB;
  word-wrap: break-word;
  
  h3 {
    margin: 0px;
    #color: #23A9F2;
    #color: #296ADC;
  }
`;

const FormTitle = styled.div`
  font-size: 2.5em;
  font-weight: bold;
  color: #45f5a5;
`;

const ContentMain = styled.div`
  display: flex;
  justify-content: center;
  width: 100%;
`;

const FormContent = styled.div`
  display: flex;
  flex-direction: column;
  text-align: left;
  color: #DDEBF5;
  width: 600px;

  h3 {
    margin-top: 10px;
    margin-bottom: 10px;
  }
  h4 {
    font-weight: bold;
    margin-top: 10px;
    margin-bottom: 5px;
    color: #7E97A7;
  }
  p {
    margin: 0px;
    margin-bottom: 5px;
  }
`;

const FieldLayout = styled.div`
  display: flex;
  flex-direction: row;
  line-height: 30px;

  input {
    height: 20px;
    width: 150px;
  }
  input[type=submit] {
    width: 250px;
    height: 50px;
    font-size: 16px;
    border: 2px solid #24282B;
    box-sizing: border-box;
    border-radius: 8px;
    :hover {
      background: #EC008C;
      color: white
    }
  }
`;

const InputDetails = styled.div`
  display: flex;
  flex-direction: column;
  
  p {
    font-weight: bold;
    font-size: 12px;
    color: red;
    margin: 0px;
  }
`;

const OptionList = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  color: black;
  height: 70px;
  line-height: 70px;
  text-align: center;
`;

export  {FullCentredLayout, BackgroundImage, Content, ContentMain, FormTitle, FormContent, FieldLayout, InputDetails, OptionList}