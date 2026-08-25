"""The orchestrator's browser console — a repo-URL form with CI/CD actions.

Served at ``GET /`` (agent-core wires ``Agent.console_html`` into the service).

The page lets the user pick each tool from a dropdown (SAST, SCA, artifact repo,
registry, monitoring, …) and fill only the fields that tool needs — collected at
run time, so there is no config-file editing and no database. The Run buttons
POST to ``/run`` with an ``input`` string; the LLM brain routes to the
``run_ci_agent`` / ``run_cd_agent`` tool.

SECURITY NOTE: this console goes through the LLM brain, so secret field values
(passwords / tokens) are NOT injected into the prompt — they are sent as
``[provided via UI]`` markers only. When real tool integration is added, deliver
the actual secrets to the pipeline via a secrets mechanism (env vars / secret
store), not through the model. No build step, no CDN.
"""

CONSOLE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NetCore CI/CD Orchestrator</title>
<style>
  :root { color-scheme: light dark; --bd:#8883; --accent:#3b82f6; --accent2:#16a34a;
          --muted:#8a94a6; --card:#8881; }
  * { box-sizing: border-box; }
  body { font: 15px/1.55 system-ui, -apple-system, sans-serif; max-width: 960px;
         margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.4rem; margin: 0 0 .2rem; }
  .sub { opacity: .6; margin-bottom: 1rem; font-size: .9rem; }
  label.fld { font-weight: 600; font-size: .8rem; text-transform: uppercase;
          letter-spacing: .04em; opacity: .72; display:block; margin-bottom:.25rem; }
  input[type=text], input[type=password], input[type=email], select {
        width: 100%; padding: .6rem .7rem; font: 14px ui-monospace, monospace;
        border: 1px solid var(--bd); border-radius: 8px; background: var(--card); color: inherit; }

  details.sec { border: 1px solid var(--bd); border-radius: 12px; margin: .7rem 0 0; overflow: hidden; }
  details.sec > summary { list-style: none; cursor: pointer; padding: .7rem .95rem;
        display: flex; align-items: center; gap: .55rem; font-weight: 700; font-size: .82rem;
        text-transform: uppercase; letter-spacing: .05em; opacity: .82; user-select: none; }
  details.sec > summary::-webkit-details-marker { display: none; }
  details.sec > summary .chev { transition: transform .18s ease; opacity: .6; font-weight: 400; }
  details.sec[open] > summary .chev { transform: rotate(90deg); }
  details.sec > summary .tag { margin-left: auto; font-weight: 500; font-size: .68rem;
        letter-spacing: .04em; text-transform: none; color: var(--muted); }
  details.sec[open] > summary { border-bottom: 1px solid var(--bd); }
  .body { padding: .5rem 1rem 1rem; }

  .catrow { padding: .7rem 0; border-bottom: 1px dashed var(--bd); }
  .catrow:last-child { border-bottom: 0; }
  .catrow > .fld { margin-bottom: .3rem; }
  .catfields { margin-top: .6rem; }
  .catfields .none { font-size: .82rem; opacity: .6; font-style: italic; padding: .3rem 0; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem 1rem; }
  @media (max-width: 640px){ .grid { grid-template-columns: 1fr; } }
  .full { grid-column: 1 / -1; }

  .opts { display: flex; gap: 1rem 1.2rem; flex-wrap: wrap; align-items: center; margin: .9rem 0 .2rem; }
  label.chk { font-size: .87rem; opacity: .9; display: flex; align-items: center; gap: .4rem; cursor: pointer; }
  .grp { display:flex; gap:.7rem; align-items:center; }
  .actions { display: flex; gap: .6rem; margin: 1.2rem 0 .3rem; flex-wrap: wrap; }
  button { flex: 1 1 220px; padding: .75rem 1rem; font-size: .95rem; font-weight: 700;
           cursor: pointer; border: 0; border-radius: 9px; color: #fff; }
  #runCi { background: var(--accent); } #runCd { background: var(--accent2); }
  pre { margin: .3rem 0 0; padding: .9rem; background: var(--card); border: 1px solid var(--bd);
        border-radius: 10px; white-space: pre-wrap; word-break: break-word;
        font: 12px ui-monospace, monospace; max-height: 380px; overflow:auto; }
  .caphint { font-size:.78rem; opacity:.55; margin:.9rem 0 .1rem; }
  .links { opacity: .6; font-size: .8rem; margin-top: 1.1rem; }
  .links a { color: var(--accent); }
</style></head>
<body>
  <h1>.NET Core CI/CD Orchestrator</h1>
  <div class="sub">Provide a Git repository URL, pick your tools, then choose which agent to run.</div>

  <label class="fld" for="repo">Git repository URL</label>
  <input id="repo" type="text" placeholder="https://github.com/your-org/your-repo.git">

  <div class="caphint">Config &amp; credentials are collapsed by default — expand a section, pick a tool, and its fields appear.</div>

  <details class="sec">
    <summary><span class="chev">&#9654;</span> CI — tools &amp; credentials <span class="tag">pick a tool per capability</span></summary>
    <div class="body" id="ciHost"></div>
  </details>

  <details class="sec">
    <summary><span class="chev">&#9654;</span> CD — deployment target <span class="tag">optional · click to override</span></summary>
    <div class="body">
      <div class="catrow" id="platformHost"></div>
      <div class="grid" style="margin-top:.6rem">
        <div><label class="fld">Kubernetes cluster</label><input id="cluster" type="text" placeholder="aks-prod-cluster"></div>
        <div><label class="fld">Namespace</label><input id="ns" type="text" placeholder="production"></div>
        <div><label class="fld">Application name</label><input id="app" type="text" placeholder="sample-api"></div>
        <div><label class="fld">Container name</label><input id="container" type="text" placeholder="sample-api"></div>
        <div class="full"><label class="fld">Playwright test repo URL</label><input id="pw" type="text" placeholder="https://github.com/your-org/sample-api-e2e.git"></div>
        <div><label class="fld">DAST severity threshold</label>
          <select id="dastSev"><option>critical</option><option selected>high</option><option>medium</option></select></div>
        <div><label class="fld">Kubeconfig / access token</label><input id="kube" type="password" placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;"></div>
      </div>
    </div>
  </details>

  <details class="sec">
    <summary><span class="chev">&#9654;</span> Approvals &amp; notifications <span class="tag">optional · click to override</span></summary>
    <div class="body"><div class="grid">
      <div><label class="fld">PROD approver name</label><input id="apprName" type="text" placeholder="Release Manager"></div>
      <div><label class="fld">PROD approver email</label><input id="apprEmail" type="email" placeholder="release-manager@example.com"></div>
      <div><label class="fld">Change management system</label><input id="cm" type="text" placeholder="ServiceNow"></div>
      <div><label class="fld">Change request ID</label><input id="cr" type="text" placeholder="CHG0012345"></div>
      <div class="full"><label class="fld">Notification emails (comma-separated)</label><input id="notify" type="text" placeholder="devops-team@example.com, on-call@example.com"></div>
    </div></div>
  </details>

  <details class="sec">
    <summary><span class="chev">&#9654;</span> Monitoring &amp; logging <span class="tag">pick a tool per capability</span></summary>
    <div class="body" id="monHost"></div>
  </details>

  <div class="opts">
    <label class="chk"><input id="optPr" type="checkbox" checked> open pull request</label>
    <label class="chk"><input id="optLlm" type="checkbox"> LLM fallback</label>
    <label class="chk"><input id="optDast" type="checkbox" checked> DAST</label>
    <label class="chk"><input id="optPw" type="checkbox" checked> Playwright gate</label>
    <span class="grp">CD handoff:
      <label class="chk"><input type="radio" name="handoff" value="auto" checked> auto</label>
      <label class="chk"><input type="radio" name="handoff" value="manual"> manual</label>
    </span>
    <label class="chk"><input id="optAuto" type="checkbox"> deploy automatically</label>
  </div>

  <div class="actions">
    <button id="runCi">Run CI Agent &#9654;</button>
    <button id="runCd">Run CD Agent &#9654;</button>
  </div>

  <pre id="out">Response will appear here.</pre>
  <div class="links">
    POST <code>/run</code> &nbsp;·&nbsp; <a href="/docs">/docs</a> &nbsp;·&nbsp; <a href="/healthz">/healthz</a>
  </div>

  <script>
    const $ = id => document.getElementById(id);

    // --- Tool catalog: each capability -> interchangeable tools -> the fields it needs ---
    const F = (id,label,type,ph) => ({id,label,type:type||'text',ph:ph||''});
    const CI_CATS = [
      { key:'coverage', label:'Code coverage & quality', tools:{
        'SonarQube':   [F('url','Host URL','text','https://sonar.example.com'), F('token','Token','password')],
        'SonarCloud':  [F('org','Organization','text'), F('token','Token','password')],
        'Codecov':     [F('token','Upload token','password')],
      }},
      { key:'sast', label:'SAST (static analysis)', tools:{
        'Fortify SSC': [F('url','SSC URL','text','https://ssc.example.com'), F('token','Auth token','password')],
        'Checkmarx':   [F('url','Base URL','text'), F('id','Client ID','text'), F('secret','Client secret','password')],
        'Semgrep':     [F('token','App token','password')],
      }},
      { key:'sca', label:'SCA (dependency scan)', tools:{
        'Sonatype Nexus IQ': [F('url','IQ Server URL','text'), F('token','Auth token','password')],
        'Snyk':              [F('org','Organization ID','text'), F('token','API token','password')],
      }},
      { key:'dast', label:'DAST (dynamic scan)', tools:{
        'Fortify WebInspect': [F('url','Scanner URL','text'), F('token','API token','password')],
        'OWASP ZAP':          [F('url','Target URL','text'), F('key','API key','password')],
      }},
      { key:'imgscan', label:'Container image scan', tools:{
        'Wiz':    [F('id','Client ID','text'), F('secret','Client secret','password')],
        'Trivy':  [],
        'Aqua':   [F('url','Server URL','text'), F('token','Token','password')],
      }},
      { key:'artifact', label:'Artifact repository', tools:{
        'Nexus':             [F('url','Repository URL','text','https://nexus.example.com/repository/…'), F('user','Username','text'), F('pass','Password','password')],
        'JFrog Artifactory': [F('url','Base URL','text'), F('token','Access token','password')],
        'GitHub Packages':   [F('owner','Owner / org','text'), F('pat','Personal access token','password')],
        'GitLab Registry':   [F('url','Registry URL','text'), F('token','Deploy token','password')],
      }},
      { key:'registry', label:'Container registry', tools:{
        'Azure ACR':  [F('server','Login server','text','myregistry.azurecr.io'), F('user','Username','text'), F('pass','Password','password')],
        'Docker Hub': [F('user','Username','text'), F('token','Access token','password')],
        'GHCR':       [F('owner','Owner','text'), F('pat','PAT','password')],
        'AWS ECR':    [F('region','Region','text','us-east-1'), F('akid','Access key ID','text'), F('secret','Secret access key','password')],
      }},
    ];
    const MON_CATS = [
      { key:'metrics', label:'Metrics / APM', tools:{
        'Dynatrace': [F('env','Environment ID','text'), F('token','API token','password')],
        'Datadog':   [F('api','API key','password'), F('app','App key','password')],
        'New Relic': [F('license','License key','password')],
      }},
      { key:'logs', label:'Log aggregation', tools:{
        'Splunk':      [F('url','HEC URL','text','https://splunk.example.com:8088'), F('token','HEC token','password')],
        'Elastic/ELK': [F('url','Elasticsearch URL','text'), F('key','API key','password')],
      }},
    ];
    const CD_PLATFORM = { key:'platform', label:'Deployment platform', tools:{
        'Harness':  [F('org','Org identifier','text'), F('proj','Project identifier','text'), F('key','API key','password')],
        'Argo CD':  [F('url','Server URL','text'), F('token','Auth token','password')],
        'Flux':     [F('url','Git source URL','text')],
    }};

    // --- Dynamic renderer: a dropdown per capability; selecting a tool shows its fields ---
    function renderCategory(host, cat){
      const wrap = document.createElement('div'); wrap.className = 'catrow';
      const lab = document.createElement('label'); lab.className = 'fld'; lab.textContent = cat.label;
      const sel = document.createElement('select'); sel.id = 'sel__' + cat.key;
      sel.innerHTML = '<option value="">— not used —</option>' +
        Object.keys(cat.tools).map(t => '<option>' + t + '</option>').join('');
      const fields = document.createElement('div'); fields.id = 'f__' + cat.key; fields.className = 'catfields';
      sel.onchange = () => {
        fields.innerHTML = '';
        const t = sel.value; if (!t) return;
        const defs = cat.tools[t];
        if (!defs.length) { fields.innerHTML = '<div class="none">No credentials required — runs in-pipeline.</div>'; return; }
        const grid = document.createElement('div'); grid.className = 'grid';
        defs.forEach(fd => {
          const d = document.createElement('div');
          d.innerHTML = '<label class="fld">' + fd.label + '</label>' +
            '<input id="fld__' + cat.key + '__' + fd.id + '" type="' + fd.type + '" placeholder="' + fd.ph + '">';
          grid.appendChild(d);
        });
        fields.appendChild(grid);
      };
      wrap.append(lab, sel, fields);
      host.appendChild(wrap);
    }
    CI_CATS.forEach(c => renderCategory($('ciHost'), c));
    MON_CATS.forEach(c => renderCategory($('monHost'), c));
    renderCategory($('platformHost'), CD_PLATFORM);

    // Collect selections. Secret fields (passwords/tokens) are NOT sent to the
    // model — they become "[provided via UI]" markers so nothing sensitive lands
    // in the LLM prompt.
    function collect(cats){
      const out = {};
      cats.forEach(cat => {
        const t = ($('sel__' + cat.key) || {}).value;
        if (!t) return;
        const vals = { tool: t };
        (cat.tools[t] || []).forEach(fd => {
          const el = $('fld__' + cat.key + '__' + fd.id);
          const v = el ? el.value.trim() : '';
          if (fd.type === 'password') { if (v) vals[fd.label] = '[provided via UI]'; }
          else if (v) { vals[fd.label] = v; }
        });
        out[cat.label] = vals;
      });
      return out;
    }

    function options(){
      return {
        open_pr: $('optPr').checked, allow_llm_fallback: $('optLlm').checked,
        include_dast: $('optDast').checked, include_playwright: $('optPw').checked,
        cd_handoff: document.querySelector('input[name=handoff]:checked').value,
        auto_deploy: $('optAuto').checked,
      };
    }

    async function run(kind){
      const url = $('repo').value.trim();
      if (!url) { $('out').textContent = 'Enter a Git repository URL first.'; return; }
      let spec;
      if (kind === 'ci') {
        spec = { agent:'NetcoreCIAgent', repo_url:url, options:options(),
                 selected_tools:collect(CI_CATS), monitoring:collect(MON_CATS) };
      } else {
        spec = { agent:'NetcoreCDAgent', repo_url:url, options:options(),
                 platform:collect([CD_PLATFORM]),
                 deployment:{ kubernetes_cluster:$('cluster').value.trim(), namespace:$('ns').value.trim(),
                   app_name:$('app').value.trim(), container_name:$('container').value.trim(),
                   playwright_repo:$('pw').value.trim(), dast_severity_threshold:$('dastSev').value,
                   kube_token: $('kube').value.trim() ? '[provided via UI]' : '' },
                 approvals:{ approver_name:$('apprName').value.trim(), approver_email:$('apprEmail').value.trim(),
                   change_system:$('cm').value.trim(), change_request:$('cr').value.trim(),
                   notify:$('notify').value.split(',').map(s=>s.trim()).filter(Boolean) },
                 monitoring:collect(MON_CATS) };
      }
      const verb = kind === 'ci' ? 'Generate a CI pipeline' : 'Generate a CD pipeline';
      const input = verb + ' for ' + url + '. Configuration selected in the UI ' +
        '(secret values shown as [provided via UI], not included):\\n' + JSON.stringify(spec, null, 2);

      $('out').textContent = 'Running ' + kind.toUpperCase() + ' agent...';
      $('runCi').disabled = $('runCd').disabled = true;
      try {
        const r = await fetch('/run', { method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({ input }) });
        const t = await r.text();
        let pretty; try { pretty = JSON.stringify(JSON.parse(t), null, 2); } catch { pretty = t; }
        $('out').textContent = (r.ok ? '' : 'HTTP ' + r.status + '\\n') + pretty;
      } catch (e) { $('out').textContent = 'Error: ' + e; }
      finally { $('runCi').disabled = $('runCd').disabled = false; }
    }
    $('runCi').onclick = () => run('ci');
    $('runCd').onclick = () => run('cd');
  </script>
</body></html>
"""
