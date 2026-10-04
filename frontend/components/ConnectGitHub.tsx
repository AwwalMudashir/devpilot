import { Icon } from "@/components/Icon"

export function ConnectGitHub({ error }: { error?: string | null }) {
  return (
    <main className="connectPage">
      <section className="connectCard">
        <div className="connectBrand">
          <span className="brandMark"><Icon name="command" size={22} /></span>
          <div>
            <strong>DevPilot</strong>
            <span>Project intelligence</span>
          </div>
        </div>

        <div className="connectLayout">
          <div className="connectOverview">
            <p className="eyebrow">Your projects, in one clear workspace</p>
            <h1>Understand what needs attention without checking every tab</h1>
            <p className="connectIntro">
              DevPilot brings repository activity, GitHub issues, pull requests,
              and project tasks together. Ask questions about a selected project,
              turn decisions into tasks, and review changes before they are applied.
            </p>

            <div className="connectCapabilities">
              <article>
                <span><Icon name="dashboard" size={18} /></span>
                <div>
                  <h2>See the current state</h2>
                  <p>Review active work, completed tasks, blockers, and recent repository activity.</p>
                </div>
              </article>
              <article>
                <span><Icon name="message" size={18} /></span>
                <div>
                  <h2>Ask with project context</h2>
                  <p>Get answers grounded in the repository and project you currently have open.</p>
                </div>
              </article>
              <article>
                <span><Icon name="tasks" size={18} /></span>
                <div>
                  <h2>Keep actions under your control</h2>
                  <p>Create or update tasks through the assistant, with approval before every change.</p>
                </div>
              </article>
            </div>
          </div>

          <aside className="connectSetup">
            <span className="connectIcon"><Icon name="github" size={26} /></span>
            <p className="eyebrow">Get started</p>
            <h2>Connect the repositories you want DevPilot to use</h2>
            <p>
              GitHub will let you choose specific repositories during setup.
              Anything you leave unselected remains outside this workspace.
            </p>

            {error && (
              <div className="connectError" role="alert">
                <Icon name="circleAlert" size={18} />
                <span>{error}</span>
              </div>
            )}

            <a className="githubConnectButton" href="/api/devpilot/auth/github/start">
              <Icon name="github" size={19} />
              Connect GitHub
              <Icon name="external" size={16} />
            </a>

            <ol className="connectionSteps" aria-label="Connection steps">
              <li><span>1</span>Sign in with GitHub</li>
              <li><span>2</span>Select repositories</li>
              <li><span>3</span>Open your workspace</li>
            </ol>

            <div className="permissionSummary">
              <div>
                <Icon name="check" size={16} />
                <span>Read-only GitHub permissions</span>
              </div>
              <div>
                <Icon name="check" size={16} />
                <span>Access can be changed or revoked in GitHub</span>
              </div>
            </div>
          </aside>
        </div>

        <p className="connectFootnote">
          Repository access is limited to your GitHub App selection. DevPilot
          tasks stay in your DevPilot workspace and do not modify repository files.
        </p>
      </section>
    </main>
  )
}
