import "../styles/custom.css"
import 'bootstrap/dist/css/bootstrap.min.css';
import '../styles/globals.css';


function ContentApp({ Component, pageProps }) {
  return (
    <>
      <Component {...pageProps} />
    </>
    )
}

export default ContentApp
