# Building "claude-essentials": A Strategy Report for a Trending, Genuinely Useful Claude Skills Repository

## TL;DR
- **Do not build a broad "basics-to-all-roles" monorepo.** The generic-skills space is already saturated and dominated by giants (obra/superpowers ~265.8k stars; anthropics/skills ~169k; K-Dense-AI/scientific-agent-skills ~34.9k). Your realistic path to organic traction is a **narrow, verifiable, hardware/edge-AI wedge** where your own ECE credibility is highest and the supply gap is near-total — specifically an **open-silicon / VLSI + embedded + TinyML/edge-deployment** skill pack backed by real evals.
- **The single biggest differentiator available in this market is verified quality.** Multiple independent testers found that the majority of published skills make Claude's output *worse*, not better. A repo that ships an eval harness (usefulness, trigger-discovery, adversarial-discovery) and publishes skill-on vs skill-off results would be one of the few credible ones — this is your moat, not breadth.
- **Skip the "humanizing AI writing" idea as a flagship.** It is both crowded (blader/humanizer, conorbronsdon/avoid-ai-writing, plus many marketplace clones) and ethically fraught (it shades into "bypass GPTZero/Turnitin" territory). At most include one honest "avoid-AI-tells" editorial skill as a supporting item, not the headline.

## Key Findings

**1. The ecosystem is large, fast-moving, and top-heavy.** As of August 2026, the most-starred community skills framework is **obra/superpowers (~265.8k stars, created July 15, 2025, MIT, ~38 contributors, growing ~18–19k stars/month)** — a TDD/brainstorm/git-worktrees methodology, not a domain library. **anthropics/skills (~169k)** is the official reference (PDF/DOCX/XLSX/PPTX, MCP-builder, skill-creator). Other large players: **thedotmack/claude-mem (~91.5k, memory), Egonex-AI/Understand-Anything (~80.9k, codebase→knowledge-graph), code-yeongyu/oh-my-openagent (~62.1k, harness), alirezarezvani/claude-skills (~24.8k, 345+ skill "kitchen sink"), OthmanAdi/planning-with-files (~23.1k), teng-lin/notebooklm-py (~18.5k).** The domain-vertical winner is **K-Dense-AI/scientific-agent-skills (~34.9k stars, 163 validated skills, "used by 175,000+ scientists," MIT)** — importantly, it ships chained skills *and* evals, which is why it earns trust. Note SKILL.md is now an open cross-tool standard: per agentskills.io / Strapi it has been "adopted by 26+ platforms including Claude, OpenAI Codex, Gemini CLI, GitHub Copilot, Cursor, and VS Code," so anything you build is portable beyond Claude Code.

**2. The reference repos you cited split into three tiers.** Giants (anthropics/skills, superpowers-adjacent). Mid-tier viral one-idea repos (planning-with-files ~23.1k, notebooklm-py ~18.5k, claude-mem ~91.5k). And small credible niche repos: **fcakyon/phd-skills (277 stars, MIT), fcakyon/claude-codex-settings (749 stars, Apache-2.0), tomicz/fable-5-train-opus-skills-after-it-retires (377 stars, 60 forks, MIT), JimLiu/baoyu-skills (~20+ content/design skills, very high per-skill install counts ~25–31k each).** The lesson: **small repos can matter if the idea is sharp and the author is credible in the domain** — phd-skills has only 277 stars but is widely cited as the template for research skills.

**3. Saturated niches (avoid as headline):** generic "awesome-claude-skills" link lists (BehiSecc, karanb192, dozens of clones); document generation (PDF/DOCX/PPTX — owned by Anthropic itself); image/video/slide generation (baoyu, muapi); "47 essential skills" kitchen-sink packs; humanizer/AI-writing-detector skills; generic code-review/TDD (owned by superpowers). Marketplaces/registries are now numerous (claudemarketplaces.com claims 23,600+ skills, 2,700+ marketplaces; tonsofskills.com; awesomeskill.ai; mdskills.ai) — being *listed* is easy and worth ~nothing; being *trusted* is hard.

**4. The genuine supply gaps (your opportunity), with evidence:**
- **Open-silicon VLSI flow (OpenLane / Sky130 / OpenROAD RTL-to-GDSII): essentially empty.** No dedicated skill repo exists. There is early RTL-authoring supply — **bjwanneng/verilog-generator** (Verilog-2005 self-check), **Fzhiyu1/chipforge-plugin** (Icarus sim + knowledge graph), **codejunkie99/Gateflow-Plugin** (SystemVerilog, 27 skills), and notably **Midstall/claude-for-hardware** (HDL/SoC/FPGA bring-up/tapeout *with hooks + evals*). But timing closure, CDC, UVM testbench discipline, and the entire open-source tapeout flow are unserved.
- **Embedded/firmware (STM32/Zephyr/FreeRTOS, HAL, memory-map, MISRA): near-empty.** Only blog guidance (Beningo) and general hardware repos; no focused, evaluated firmware skill pack.
- **Safety-critical: split.** ISO 26262 automotive is served (jherrodthomas/automotive-skills-suite; AutoZYX-Labs). **DO-178C avionics and IEC 61508 are greenfield** — only a NASA "Power of 10" coding-patterns skill exists.
- **Space/NewSpace (orbital mechanics, GNC, rad-hardening, CubeSat flight software): essentially empty.** Only Soljourner/claude-engineering-skills touches "orbital mechanics" as one line item; NASA-PDS/pds-agent-skills is unrelated (release notes).
- **Quantum (Qiskit/Cirq/PennyLane): covered only inside K-Dense's science library and davila7/claude-code-templates** — no standalone quantum-workflow repo.
- **Post-quantum crypto migration / crypto-agility / CBOM: thin.** PQC appears only as sub-topics inside general cybersecurity suites (Masriyan, pitimon, mukul975); **CBOM (Cryptography Bill of Materials) has no dedicated skill.**
- **OT/ICS security (Modbus, PLC, IEC 62443): partially served but embedded** inside broad security suites (mukul975 has an IEC-62443-zones skill); no standalone OT/ICS repo.
- **Distillation / "train a smaller model with a stronger one": conceptually hot, thinly built.** tomicz's Fable-5 prompt (377 stars) and benjaminard/fable-skills exist, plus paid "Skill Distillation Kit" newsletters, but there is **no rigorous open eval-harness + synthetic-data + LLM-as-judge distillation toolkit** as a skill pack.
- **Meta-skills (skills for writing/evaluating skills):** partly owned by Anthropic's skill-creator and obra's writing-skills; but an **independent, open skill-evaluation/benchmarking harness** is a real gap (only MLflow's blog, and academic SkillVetBench/CONTRA/SkillRet papers exist).

**5. Moderately-served (enter only with a quality edge):** ROS2 robotics (arpitg1304/robotics-agent-skills, dbwls99706/ros2-engineering-skills *with evals*, omer-metin); AI red-teaming (yechao-zhang/red-team-agent-skills, blacklanternsecurity/red-run, SnailSploit/claude-red); LLM quantization (marketplace skills exist but shallow).

**6. What actually drives organic GitHub traction (evidence-based):**
- **README-as-product-page:** one-line value prop readable in ~7 seconds, a GIF/asciinema demo proving it works, a copy-paste install that works in under 5 minutes, 3 concrete use cases. Analyses of repos that hit 10k+ stars found the README "sells in under 7 seconds" and ~95% could be tried in <5 minutes.
- **Launch dynamics:** most repos that reach 10k+ stars launched on **Hacker News first (Show HN with a personal story), then cross-posted to Reddit/X**; Tue–Thu ~8–10am EST performs best; the personal-story framing gets ~3x more upvotes than a technical description. The **AFFiNE** project went 0→60k stars via pre-seeded Reddit communities (r/selfhosted, r/opensource) plus 28 GitHub-Trending appearances in five months; its team reports ~2,000 first-month stars from Reddit alone, and that a repo only starts "converting strangers" above ~200 stars. (A frequently-cited claim that EmbedPDF hit #1 on HN with 500+ stars in 24 hours comes from the author's own blog and could not be independently verified — treat as illustrative, not proven; EmbedPDF itself is a real Apache-2.0, PDFium-based viewer serving 1.2M+ monthly users per pdfa.org.)
- **Sustaining momentum:** contributor velocity, issue-resolution, and a healthy forks/watchers ratio matter more than the initial spike. Beware **fake-star suspicion** — a vertical 24–48h spike with no matching issues/PRs/watchers reads as manipulation and can *hurt* credibility.
- **Academic caveat:** an arXiv event-study of HN→GitHub found execution and timing dominate; license type and topic tags have minimal predictive power once quality/timing are controlled.

**7. Quality standards are now well-documented and are your differentiator.** Anthropic's guidance (equipping-agents engineering post; skill-authoring docs; skill-creator): a skill is a folder with **SKILL.md** carrying YAML frontmatter (`name`, `description` — must state *what it does* and *when to use it*), progressive disclosure (load SKILL.md first, reference files only on demand), bundled scripts run via bash without entering context. Concrete limits, now precisely documented:
  - **SKILL.md body ≤ 500 lines / ~5000 tokens** (webfuse.com "Agent Skills Cheat Sheet, 2026"); Anthropic's own guidance is blunt that "skills that exceed this measurably degrade agent performance."
  - **description field: hard cap of 1024 characters in the open spec** (agentskills.io, "Optimizing skill descriptions"); in Claude Code, **the combined description + optional `when_to_use` text is truncated at 1536 characters** in the skill listing (generativeprogrammer.com).
  - **Avoid all-caps MUST/ALWAYS/NEVER:** "Anthropic's skill-creator explicitly flags all-caps MUST/ALWAYS/NEVER as a yellow flag to reframe" (generativeprogrammer.com) — prefer "explain-the-why."
  - Distribution: a plugin bundles skills; a **marketplace is a GitHub repo with `.claude-plugin/marketplace.json`** distributing plugins. Skills differ from MCP (MCP exposes APIs/tools; skills tell the model *how* to use capabilities) and from subagents (separate context/roles).

**8. The community's loudest complaint is skill quality/bloat — which is your wedge.** Independent testing (corpwaters Substack) of 200+ skills found "most publicly available skills don't just fail to help — they actively hurt," and in one "47 essential skills" test, **40 of 47 made output worse**; the ~20% that helped were "built by people who actually know the domain… and iterated on evaluation." Per Addy Osmani's "Audit your Agent files," **"a June study of 100 popular repositories found lint-related leakage in 62%, context bloat in 42%, and skill leakage in 35%."** MindStudio and others repeatedly warn that installing too many skills degrades performance via context-window bloat.

## Details

### Landscape map (named, with numbers)
| Repo | ~Stars | What it is | Note |
|---|---|---|---|
| obra/superpowers | 265.8k | TDD/brainstorm methodology framework | Most-starred; marketplace + separate skills repo + lab (hub-and-spoke) |
| anthropics/skills | 169k | Official skills (docs, office, skill-creator) | The reference implementation |
| thedotmack/claude-mem | 91.5k | Persistent memory | Not a domain library |
| Egonex-AI/Understand-Anything | 80.9k | Codebase→knowledge graph | |
| code-yeongyu/oh-my-openagent | 62.1k | Multi-harness agent | Provocative marketing |
| K-Dense-AI/scientific-agent-skills | 34.9k | 163 science skills + evals | Vertical winner; the model to emulate |
| alirezarezvani/claude-skills | 24.8k | 345+ skill kitchen sink | Breadth, unclear per-skill quality |
| OthmanAdi/planning-with-files | 23.1k | File-based planning | One sharp idea |
| teng-lin/notebooklm-py | 18.5k | NotebookLM API + skill | |
| fcakyon/claude-codex-settings | 749 | Personal CC/Codex setup | |
| tomicz/fable-5-…-retires | 377 | Distillation prompt | Went viral on X |
| fcakyon/phd-skills | 277 | PhD research skills | Small but influential template |

Anthropic's own repo owning document-generation is why that niche is a dead end for outsiders. The hub-and-spoke pattern obra uses (a marketplace repo, a community-editable skills repo, an experimental lab repo) is the closest proven analogue to what you should build.

### The "humanizing AI writing" angle — verdict: not a flagship
Demand is real. The linguistic "tells" are now academically documented: Kobak et al. (*Science Advances*, July 2 2025, DOI 10.1126/sciadv.adt3813) analyzed "more than 15 million biomedical abstracts" and found "at least 13.5% of 2024 abstracts were processed with LLMs" (up to 40% in some subcorpora), with **"delves" the single most over-represented excess word.** Wikipedia's "Signs of AI writing" further notes LLMs "overuse the rule of three" and em dashes (a July-2026 study found that among current models only Claude used em dashes more than professional writers, while ChatGPT used them less). But supply is already thick: **blader/humanizer** (35 patterns, actively versioned), **conorbronsdon/avoid-ai-writing** (21 categories, 112-entry replacement table, two-pass detection), plus marketplace clones ("avoid-ai-writing," "ai-anti-pattern-detector," "humanizer"). Worse, much of the category bleeds into **"bypass GPTZero/Turnitin/Originality.ai"** (e.g., "undetectable-ai-humanizer"), which is ethically and reputationally risky — associating your repo with academic-dishonesty tooling would undercut the "serious technical audience" you want. Recommendation: if included at all, ship a single tasteful **`prose-de-slop`** editorial skill grounded in the Wikipedia/Kobak evidence, framed as writing quality (not detector evasion), and do not lead with it.

### Distillation ("Fable-5 style") — a strong *secondary* wedge
The "have the smart model write skills for the cheap model" meme (tomicz, benjaminard/fable-skills) is popular but shallow: it's mostly prompts, not measured. The honest framing — repeated by every credible write-up — is that **you cannot transfer capacity via markdown; you can move the model's checkpoints/process** (verify-before-claim, root-cause-before-fix). A genuinely novel contribution would be a **distillation-and-eval skill pack**: synthetic-data generation, an LLM-as-judge grader rubric, a blind skill-on/skill-off test template, and reproducible win/loss reporting. This directly serves your stated "train smaller models using stronger models" interest and plugs the meta-skill/eval gap simultaneously.

### Quality/eval mechanics you should adopt
Emulate the two repos that already do this well: **Midstall/claude-for-hardware** (hooks that mechanically enforce house style; evals for usefulness, discovery, adversarial-discovery — "measured, not asserted") and **dbwls99706/ros2-engineering-skills** (eval_runner.py, fixture-integrity checks, explicit statements about what a passing test does *not* prove). Add MLflow-style LLM-as-judge scoring (the six-judge pattern: did the skill get invoked, were artifacts created, was the sequence followed). Publish results in the README. This is the single practice that separates the trusted ~20% from the noise.

### Architecture decision — recommended structure
**Recommendation: one flagship hub repo + a plugin marketplace manifest, with room to spin out at most 1–2 specialized repos later.** Rationale:
- **Star concentration:** oh-my-zsh has ~10x the stars of its nearest competitor (prezto) because newcomers concentrate on one canonical hub. Splitting into many repos on day one fragments stars and kills discoverability. Keep one repo as the front door.
- **Maintenance:** a solo pre-final-year student cannot maintain an org of 15 repos. A monorepo lets you run one CI/eval pipeline across all skills.
- **Marketplace mechanics:** ship `.claude-plugin/marketplace.json` + `plugin.json` so users install with `/plugin marketplace add <you>/claude-essentials` — this is the modern, low-friction path and signals you understand the platform.
- **When to spin out:** only when a vertical (e.g., VLSI) grows its own contributor base and release cadence — mirror obra's hub-and-spoke (core + community-skills + lab).

Proposed layout:
```
claude-essentials/
├── README.md                 # hero framing, GIF, <60s quickstart, honest scope, eval results table
├── .claude-plugin/
│   ├── marketplace.json       # distributes the plugin(s)
│   └── plugin.json
├── skills/
│   ├── rtl-verilog-lint/      # SKILL.md + references/ + scripts/ + evals/
│   ├── testbench-uvm/
│   ├── timing-closure-cdc/
│   ├── openlane-sky130-flow/
│   ├── embedded-misra-static/
│   ├── onnx-quantize-tflm/    # your ONNX/edge-AI credibility
│   └── skill-distillation-eval/
├── evals/                     # usefulness / discovery / adversarial-discovery harness
│   └── eval.yaml
├── hooks/                     # enforce style + frontmatter/line-limit checks in CI
├── .github/workflows/test.yml
├── CONTRIBUTING.md            # skill template, eval requirement, license/attribution rules
├── LICENSE                    # MIT (permissive, maximal reuse) or Apache-2.0
└── docs/
```
Each SKILL.md: body ≤500 lines/≤5000 tokens; description ≤1024 chars (≤1536 combined with `when_to_use` for Claude Code); "explain-the-why" instead of all-caps imperatives.

### 90-day execution sequence
- **Weeks 1–2 (wedge + credibility audit):** Pick the wedge where *your* ECE background is strongest and supply is thinnest. Recommended: **open-silicon + embedded/edge-AI**. Build the eval harness *first* (usefulness/discovery/adversarial) so every skill ships measured.
- **Weeks 3–6 (build the MVP slice — depth over breadth):** Ship **5–7 genuinely excellent skills**, not 30 shallow ones. Candidate flagship: an **OpenLane/Sky130 RTL-to-GDSII flow skill** (completely empty gap) or a **Verilog/SystemVerilog lint + UVM testbench discipline** pack, plus one **ONNX/TinyML quantization→TFLite-Micro deployment** skill that leans on your model-optimization expertise. Each skill: SKILL.md <500 lines, sharp trigger description, references/ + scripts/, and a published skill-on/skill-off result.
- **Weeks 7–8 (assets + honesty):** Record 2–3 asciinema/GIF demos of the killer skill. Write an honest scope statement ("covers X, does not cover Y; verified on these cases"). Add CONTRIBUTING.md with a skill template and a **mandatory eval gate** for PRs. Add correct attribution/licenses (never copy other repos' SKILL.md text).
- **Weeks 9–10 (pre-seed):** Spend two weeks being genuinely helpful in r/FPGA, r/embedded, r/chipdesign, r/ClaudeAI, and relevant Discords *before* launching — build karma/credibility (this is precisely what AFFiNE credits for its first ~2,000 Reddit stars).
- **Week 11 (launch):** Publish a **Show HN with a personal story** ("I'm an ECE student; I got tired of Claude writing non-synthesizable Verilog, so I built and *measured* skills that fix it"), Tue–Thu ~8–10am EST, with the demo GIF and the eval table front-and-center. Same day, cross-post to the pre-seeded subreddits and X. Submit to the credible awesome-lists and marketplaces as a *secondary* channel.
- **Weeks 12–13 (sustain):** Respond to every issue within 24h, merge good PRs fast, publish a short "what the evals showed" follow-up, and only then consider a second vertical.

### Metrics to watch (and thresholds that change the plan)
- **Leading:** HN front-page rank, unique README→install referral sources, `/plugin install` mentions, issue open→close time.
- **Health (not vanity):** forks/stars ratio (>10% healthy), watchers/stars ratio (anomalously low = marketing-only signal), contributor count over 90 days.
- **Thresholds:** the AFFiNE data suggests organic distribution only ignites above ~200 real stars — clear that first. If you then clear ~500 real stars from organic sources and >3 external contributors in 30 days, spin out the strongest vertical and double down. If skills fail their own evals, *pull them* — a smaller measured repo beats a large unverified one.

## Recommendations
1. **Commit to the open-silicon/embedded/edge-AI wedge.** It is the largest true greenfield (OpenLane/Sky130, embedded/MISRA, TinyML deployment) *and* aligns with your demonstrable credibility — the exact combination corpwaters says produces the trusted ~20%.
2. **Ship evals before skills.** Make "measured, not asserted" your tagline. Copy the Midstall/claude-for-hardware and dbwls99706 eval patterns; publish skill-on/skill-off tables.
3. **Depth over breadth: 5–7 excellent skills at launch.** Explicitly reject the 30-directory plan — breadth is where credibility goes to die and where context-bloat complaints (62%/42%/35% leakage) originate.
4. **One hub repo + marketplace manifest; spin out later.** MIT license. Correct attribution. `.claude-plugin/marketplace.json`.
5. **Launch as a Show HN story, pre-seed communities first, cross-post second.** Lead with a demo GIF and eval results, not feature lists.
6. **Treat "humanizer" and generic distillation memes as garnish, not entrées.** If you build distillation, make it the *rigorous eval* version nobody else has.
7. **Add one meta-skill: an open skill-evaluation harness.** It plugs a real gap, showcases your quality bar, and recruits contributors who care about rigor.

## Caveats
- **Star counts are live-page, rounded values (Aug 2026) and move fast** (superpowers gains ~18k/month); treat all figures as approximate. Exact repo creation dates are not exposed on GitHub landing pages and were estimated from repo IDs and README references.
- **The market may cool.** "Skills" enthusiasm peaked in early–mid 2026 with heavy hype and backlash; a repo launched now competes with fatigue and skepticism — which is *why* verifiability matters more than novelty.
- **Frontier-domain gaps are real but so is thin demand.** DO-178C, space/GNC, PQC-CBOM are genuinely empty *partly because* the professional audiences are small and often can't run cloud AI on regulated/classified code. Empty ≠ automatically valuable; validate demand (Reddit/issues) before over-investing. The embedded/VLSI/TinyML wedge is safer because those communities are large and active.
- **Some evidence is secondary** (Medium/Substack posts, marketplace aggregators). Star counts and the existence of specific repos are well-corroborated; single-source claims — "175,000 scientists," "40 of 47 skills made output worse," the 62%/42%/35% leakage study, and the EmbedPDF launch metric — should be cited as such, not treated as settled fact.
- **A solo student maintaining momentum is the top failure risk.** The graveyard is full of high-star skill repos that went stale; a small, evaluated, actively-maintained repo beats a large abandoned one for the "serious technical audience" you're targeting.