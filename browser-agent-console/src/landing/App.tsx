import './App.css'

export default function App() {
  return (
    <main className="landing-page" aria-label="Claude code for building extensions">
      <img className="brand-mark" src="/landing-assets/stack-logo.png" alt="Browser Forge" />

      <section className="hero" aria-labelledby="hero-title">
        <h1 id="hero-title">
          claude code for building
          <span>extensions</span>
        </h1>
        <p>web browsing should be personalized, take a look in chrome!</p>
        <a className="try-button" href="https://agentverse.ai/agents/details/agent1q0a82jftlsmgjnuxw32mm2ewhtsyr4mnhke8tnmxv34nra5qjz8uzvmwgkw/profile" target="_blank" rel="noreferrer">try it out :)</a>
      </section>

      <footer className="landing-footer" aria-label="Project links">
        <nav>
          <a href="https://github.com/aidanjnn/the-extension" rel="noreferrer">github</a>
          <span aria-hidden="true">|</span>
          <a href="#demo">demo vid!</a>
        </nav>
      </footer>
    </main>
  )
}
