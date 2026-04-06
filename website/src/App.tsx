import {
  ArrowRight,
  Bot,
  Cable,
  Code2,
  Command,
  FolderKanban,
  Globe,
  MessagesSquare,
  ShieldCheck,
  Sparkles,
  Workflow,
  Wrench,
} from 'lucide-react'
import { motion } from 'motion/react'
import './App.css'

const proofPoints = [
  {
    value: '99% fewer LOC',
    label: 'than OpenClaw',
    detail: 'Nanobot keeps the core agent surface small, auditable, and fast to modify.',
  },
  {
    value: '2-minute path',
    label: 'from install to first run',
    detail: 'Clone, install, onboard, and start chatting without a full platform rollout.',
  },
  {
    value: '11+ channels',
    label: 'ready out of the box',
    detail: 'Telegram, Discord, Slack, WhatsApp, Matrix, Email, WeChat, and more.',
  },
  {
    value: 'Supervisor model',
    label: 'for long-running work',
    detail: 'Use bounded cycles, short-lived workers, and workspace state as the durable brain.',
  },
]

const featurePillars = [
  {
    icon: Bot,
    title: 'Lightweight by design',
    body: 'Small codebase, low ceremony, and fewer moving parts than heavyweight agent stacks.',
  },
  {
    icon: MessagesSquare,
    title: 'Multi-channel delivery',
    body: 'Run the same assistant across chat apps without rebuilding the core logic each time.',
  },
  {
    icon: Cable,
    title: 'MCP and tool integration',
    body: 'Register external MCP servers and use them alongside built-in shell, web, file, and cron tools.',
  },
  {
    icon: Workflow,
    title: 'Focused long-running agents',
    body: 'Keep progress inspectable with supervisor-worker loops, durable files, and explicit promotion gates.',
  },
]

const channels = [
  'Telegram',
  'Discord',
  'Slack',
  'WhatsApp',
  'Feishu',
  'WeChat',
  'DingTalk',
  'Matrix',
  'Email',
  'QQ',
  'Wecom',
  'Mochat',
]

const workflow = [
  {
    title: 'Read current state',
    body: 'Treat the workspace as the durable brain instead of relying on one endless chat thread.',
  },
  {
    title: 'Pick one bounded task',
    body: 'Keep scope narrow: one subject, one artifact, one decision at the end.',
  },
  {
    title: 'Spawn short-lived workers',
    body: 'Use role-specific subagents when they improve clarity, not as recursive managers.',
  },
  {
    title: 'Review and write back',
    body: 'Update durable files, measure the result, then decide to reject, revise, test, or promote.',
  },
]

const commandBlocks = [
  {
    title: 'Install from source',
    icon: Command,
    code: `git clone https://github.com/HKUDS/nanobot.git
cd nanobot
pip install -e .`,
  },
  {
    title: 'Bootstrap the assistant',
    icon: Wrench,
    code: `nanobot onboard --wizard

# then start chatting
nanobot agent`,
  },
]

const configSnippet = `{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "provider": "openrouter"
    }
  }
}`

function App() {
  return (
    <div className="site-shell">
      <div className="site-background" aria-hidden="true" />

      <header className="topbar">
        <a className="brand" href="#top">
          <img src="/nanobot-logo.png" alt="Nanobot logo" />
          <span>nanobot</span>
        </a>

        <nav className="nav-links" aria-label="Primary">
          <a href="#features">Features</a>
          <a href="#workflow">Workflow</a>
          <a href="#quickstart">Quick start</a>
        </nav>
      </header>

      <main id="top">
        <section className="hero section">
          <motion.div
            className="hero-copy"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
          >
            <div className="eyebrow">
              <Sparkles size={16} />
              <span>Ultra-lightweight personal AI assistant</span>
            </div>

            <h1>Build a serious AI assistant without inheriting a giant framework.</h1>

            <p className="hero-text">
              Nanobot packages multi-provider agents, multi-channel delivery, MCP tooling, cron,
              and long-running supervisor workflows into a codebase that stays readable enough to
              actually change.
            </p>

            <div className="hero-actions">
              <a className="button button-primary" href="https://github.com/HKUDS/nanobot">
                View GitHub
                <ArrowRight size={18} />
              </a>
              <a className="button button-secondary" href="#quickstart">
                See quick start
              </a>
            </div>

            <ul className="signal-row" aria-label="Key product signals">
              <li>v0.1.4.post6</li>
              <li>Python 3.11+</li>
              <li>Client-rendered React site</li>
              <li>MIT licensed</li>
            </ul>
          </motion.div>

          <motion.div
            className="hero-panel"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.15, ease: 'easeOut' }}
          >
            <div className="hero-panel-header">
              <span>Why it lands</span>
              <span>Focused, inspectable, fast</span>
            </div>

            <div className="hero-metric-card accent-card">
              <span className="metric-value">99% fewer lines of code</span>
              <p>
                Compared with OpenClaw, with a repository script that keeps the claim directly
                verifiable.
              </p>
            </div>

            <div className="mini-grid">
              <article>
                <Globe size={18} />
                <strong>Multi-provider</strong>
                <p>OpenAI, Anthropic, OpenRouter, Azure OpenAI, Ollama, and more.</p>
              </article>
              <article>
                <MessagesSquare size={18} />
                <strong>Chat everywhere</strong>
                <p>Use the same assistant across Telegram, Slack, Discord, WhatsApp, and more.</p>
              </article>
              <article>
                <ShieldCheck size={18} />
                <strong>Lean security posture</strong>
                <p>Fewer dependencies, explicit tool boundaries, and recent hardening work.</p>
              </article>
              <article>
                <FolderKanban size={18} />
                <strong>Workspace-first memory</strong>
                <p>Long-running work is stored in files and artifacts, not only in chat context.</p>
              </article>
            </div>
          </motion.div>
        </section>

        <section className="section proof-grid" aria-label="Product proof">
          {proofPoints.map((item, index) => (
            <motion.article
              key={item.value}
              className="proof-card"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.45, delay: index * 0.06 }}
            >
              <span className="proof-value">{item.value}</span>
              <strong>{item.label}</strong>
              <p>{item.detail}</p>
            </motion.article>
          ))}
        </section>

        <section className="section" id="features">
          <div className="section-heading">
            <span>Core strengths</span>
            <h2>A lean agent framework that still covers the hard parts.</h2>
            <p>
              Nanobot is opinionated about small surface area, clean extension points, and
              practical operator workflows instead of maximal abstraction.
            </p>
          </div>

          <div className="feature-grid">
            {featurePillars.map((feature, index) => {
              const Icon = feature.icon
              return (
                <motion.article
                  key={feature.title}
                  className="feature-card"
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.45, delay: index * 0.08 }}
                >
                  <div className="feature-icon">
                    <Icon size={22} />
                  </div>
                  <h3>{feature.title}</h3>
                  <p>{feature.body}</p>
                </motion.article>
              )
            })}
          </div>
        </section>

        <section className="section split-section">
          <div className="section-heading compact">
            <span>Channel support</span>
            <h2>One agent, many front doors.</h2>
            <p>
              Ship the same assistant to chat apps your users already live in, without maintaining
              separate product stacks for each integration.
            </p>
          </div>

          <div className="channel-cloud" aria-label="Supported chat platforms">
            {channels.map((channel) => (
              <span key={channel} className="channel-pill">
                {channel}
              </span>
            ))}
          </div>
        </section>

        <section className="section architecture-section">
          <div className="section-heading compact">
            <span>Architecture</span>
            <h2>Readable enough to reason about, structured enough to scale.</h2>
            <p>
              The architecture stays modular around channels, providers, tools, sessions, memory,
              cron, and the agent runtime rather than hiding everything inside one opaque app
              layer.
            </p>
          </div>

          <motion.div
            className="architecture-frame"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.55 }}
          >
            <img src="/nanobot-architecture.png" alt="Nanobot architecture diagram" />
          </motion.div>
        </section>

        <section className="section split-section" id="workflow">
          <div className="section-heading compact">
            <span>Long-running workflow</span>
            <h2>Keep open-ended agents focused instead of letting them drift.</h2>
            <p>
              Nanobot’s guide pushes a strict supervisor-worker operating model: bounded cycles,
              durable artifacts, and explicit review gates before promotion.
            </p>
          </div>

          <div className="workflow-list">
            {workflow.map((item, index) => (
              <motion.article
                key={item.title}
                className="workflow-card"
                initial={{ opacity: 0, x: -18 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.4, delay: index * 0.08 }}
              >
                <div className="workflow-number">0{index + 1}</div>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </div>
              </motion.article>
            ))}
          </div>
        </section>

        <section className="section quickstart-section" id="quickstart">
          <div className="section-heading">
            <span>Quick start</span>
            <h2>Install it, point it at a provider, and start chatting.</h2>
            <p>
              The getting-started path is direct: install, run onboarding, set a provider, and
              launch the agent or gateway.
            </p>
          </div>

          <div className="code-layout">
            <div className="command-grid">
              {commandBlocks.map((block) => {
                const Icon = block.icon
                return (
                  <article key={block.title} className="code-card">
                    <div className="code-card-header">
                      <span className="code-icon">
                        <Icon size={16} />
                      </span>
                      <strong>{block.title}</strong>
                    </div>
                    <pre>
                      <code>{block.code}</code>
                    </pre>
                  </article>
                )
              })}
            </div>

            <article className="code-card config-card">
              <div className="code-card-header">
                <span className="code-icon">
                  <Code2 size={16} />
                </span>
                <strong>Minimal provider config</strong>
              </div>
              <pre>
                <code>{configSnippet}</code>
              </pre>
            </article>
          </div>
        </section>
      </main>

      <footer className="footer">
        <p>Nanobot is positioned for educational, research, and technical exchange use.</p>
        <div className="footer-links">
          <a href="https://github.com/HKUDS/nanobot">GitHub</a>
          <a href="https://pypi.org/project/nanobot-ai/">PyPI</a>
          <a href="https://discord.gg/MnCvHqpUGB">Community</a>
        </div>
      </footer>
    </div>
  )
}

export default App
