import Navbar from "./components/Navbar";
import Background from "./components/Background";
import Hero from "./components/Hero";
import Features from "./components/Features";
import Workflow from "./components/Workflow";
import AIWorkspace from "./components/AIWorkspace";
import Instruments from "./components/Instruments";
import Technologies from "./components/Technologies";
import WhyMaestro from "./components/WhyMaestro";
import Team from "./components/Team";

function App() {
  return (
    <>
      {/* Animated Background */}
      <Background />

      {/* Navbar */}
      <Navbar />

      {/* Hero */}
      <Hero />

      {/* Main Sections */}
      <Features />

      <Workflow />

      {/* AI Upload & Transcription Workspace */}
      <AIWorkspace />

      <Instruments />

      <Technologies />

      <WhyMaestro />

      <Team />
    </>
  );
}

export default App;