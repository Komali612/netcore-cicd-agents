"""The orchestrator's browser console — a repo-URL form with CI/CD actions.

Served at ``GET /`` (agent-core wires ``Agent.console_html`` into the service).
The two buttons POST to ``/run`` with an ``input`` string that encodes the
selected options; the LLM brain then routes to the ``run_ci_agent`` /
``run_cd_agent`` tool with those options. No build step, no CDN.
"""

CONSOLE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NetCore CI/CD Orchestrator</title>
<style>
  :root { color-scheme: light dark; --bd:#8883; --accent:#3b82f6; --accent2:#16a34a; --muted:#8a94a6; }
  * { box-sizing: border-box; }
  body { font: 15px/1.55 system-ui, -apple-system, sans-serif; max-width: 880px;
         margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.4rem; margin: 0 0 .2rem; }
  .sub { opacity: .6; margin-bottom: 1.3rem; font-size: .9rem; }
  label.fld { font-weight: 600; font-size: .82rem; text-transform: uppercase;
          letter-spacing: .04em; opacity: .75; }
  input[type=text] { width: 100%; padding: .7rem .8rem; margin-top: .35rem;
         font: 14px ui-monospace, monospace; border: 1px solid var(--bd);
         border-radius: 9px; background: #8881; }
  .actions { display: flex; gap: .6rem; margin: 1rem 0 .3rem; flex-wrap: wrap; }
  button { flex: 1 1 200px; padding: .7rem 1rem; font-size: .95rem; font-weight: 600;
           cursor: pointer; border: 0; border-radius: 9px; color: #fff; }
  #runCi { background: var(--accent); } #runCd { background: var(--accent2); }
  button:disabled { opacity: .5; cursor: wait; }
  fieldset { border: 1px solid var(--bd); border-radius: 10px; margin: .8rem 0 0; padding: .6rem .9rem 0.9rem; }
  legend { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; opacity: .6; padding: 0 .4rem; }
  .opts { display: flex; gap: 1rem 1.2rem; flex-wrap: wrap; align-items: center; }
  label.chk { font-size: .87rem; opacity: .85; display: flex; align-items: center; gap: .4rem; cursor: pointer; }
  .grp { display: flex; gap: .8rem; align-items: center; }
  pre { margin-top: 1rem; padding: .9rem; background: #8881; border: 1px solid var(--bd);
        border-radius: 10px; white-space: pre-wrap; word-break: break-word;
        min-height: 2rem; font: 12.5px ui-monospace, monospace; }
  .links { opacity: .6; font-size: .8rem; margin-top: 1.2rem; }
  .links a { color: var(--accent); }
</style></head>
<body>
  <h1>.NET Core CI/CD Orchestrator</h1>
  <div class="sub">Provide a Git repository URL, set options, then choose which agent to run.</div>

  <label class="fld" for="repo">Git repository URL</label>
  <input id="repo" type="text" placeholder="https://github.com/your-org/your-repo.git">

  <fieldset>
    <legend>Shared</legend>
    <div class="opts">
      <label class="chk"><input id="optPr" type="checkbox" checked> open pull request</label>
    </div>
  </fieldset>

  <fieldset>
    <legend>CI options</legend>
    <div class="opts">
      <label class="chk" title="If Discover can't match a built-in .NET template, let the LLM author the workflow instead of writing the repo to the exception list.">
        <input id="optLlmCi" type="checkbox"> LLM fallback (CI)</label>
      <label class="chk"><input id="optDastCi" type="checkbox" checked> DAST scan</label>
    </div>
  </fieldset>

  <fieldset>
    <legend>CD options</legend>
    <div class="opts">
      <span class="grp">CD handoff:
        <label class="chk"><input type="radio" name="handoff" value="auto" checked> auto — right after CI</label>
        <label class="chk"><input type="radio" name="handoff" value="manual"> manual — in Actions</label>
      </span>
      <label class="chk" title="Checked: deploy straight to production. Unchecked: pause for click-to-approve.">
        <input id="optAutoDeploy" type="checkbox"> deploy automatically (else click to approve)</label>
      <label class="chk"><input id="optDastCd" type="checkbox" checked> DAST gate</label>
      <label class="chk"><input id="optPlaywright" type="checkbox" checked> Playwright gate</label>
      <label class="chk" title="If no built-in deploy recipe matches the app shape, let the LLM author one.">
        <input id="optLlmCd" type="checkbox"> LLM fallback (CD)</label>
    </div>
  </fieldset>

  <div class="actions">
    <button id="runCi">Run CI Agent &#9654;</button>
    <button id="runCd">Run CD Agent &#9654;</button>
  </div>

  <pre id="out">Response will appear here.</pre>
  <div class="links">
    POST <code>/run</code> &nbsp;·&nbsp; <a href="/docs">/docs</a>
    &nbsp;·&nbsp; <a href="/healthz">/healthz</a>
  </div>

  <script>
    const $ = id => document.getElementById(id);
    const out = $('out'), repo = $('repo'), ci = $('runCi'), cd = $('runCd');

    async function run(kind) {
      const url = repo.value.trim();
      if (!url) { out.textContent = 'Enter a Git repository URL first.'; return; }
      const openPr = $('optPr').checked;
      let input;
      if (kind === 'ci') {
        input = 'Generate a CI pipeline for ' + url +
          '. Options: open_pr=' + openPr +
          ', allow_llm_fallback=' + $('optLlmCi').checked +
          ', include_dast=' + $('optDastCi').checked + '.';
      } else {
        const handoff = document.querySelector('input[name=handoff]:checked').value;
        input = 'Generate a CD pipeline for ' + url +
          '. Options: open_pr=' + openPr +
          ', auto_deploy=' + $('optAutoDeploy').checked +
          ', auto_handoff=' + (handoff === 'auto') +
          ', include_dast=' + $('optDastCd').checked +
          ', include_playwright=' + $('optPlaywright').checked +
          ', allow_llm_fallback=' + $('optLlmCd').checked + '.';
      }
      out.textContent = 'Running ' + kind.toUpperCase() + ' agent...';
      ci.disabled = cd.disabled = true;
      try {
        const r = await fetch('/run', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ input }),
        });
        const t = await r.text();
        let pretty; try { pretty = JSON.stringify(JSON.parse(t), null, 2); } catch { pretty = t; }
        out.textContent = (r.ok ? '' : 'HTTP ' + r.status + '\\n') + pretty;
      } catch (e) { out.textContent = 'Error: ' + e; }
      finally { ci.disabled = cd.disabled = false; }
    }
    ci.onclick = () => run('ci');
    cd.onclick = () => run('cd');
  </script>
</body></html>
"""
