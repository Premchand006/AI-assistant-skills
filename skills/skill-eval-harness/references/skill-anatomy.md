# Anatomy of a skill that works

Loaded on demand.

## The shape

```
skills/my-skill/
├── SKILL.md            # loaded when the skill triggers
├── references/         # loaded only when SKILL.md sends the model there
├── scripts/            # run via bash; the contents never enter context
└── evals/eval.yaml     # the evidence that any of it helps
```

Progressive disclosure is the whole design. `SKILL.md` is the part that costs
context every time the skill loads, so it holds the decision-making: what to
do, in what order, and why. Depth goes in `references/`, named from `SKILL.md`
with a sentence saying which question sends the reader there.

Scripts are the strongest part of a skill, because a script that runs is worth
more than a paragraph the model may paraphrase. Deterministic work — parsing,
checking, counting — belongs in a script; a script's source never enters the
context window unless the model reads it.

## Budgets

| Field | Limit | What happens past it |
|---|---|---|
| `SKILL.md` body | 500 lines / ~5000 tokens | measurably degrades performance |
| `description` | 1024 characters | rejected by the spec |
| `description` + `when_to_use` | 1536 characters | truncated in the Claude Code listing |

`tools/validate_skills.py` enforces all three, so a skill cannot drift past
them unnoticed.

## The description is the skill's trigger

It is the only part loaded before the skill is selected. A model choosing among
twenty skills sees twenty descriptions and nothing else, so the description has
one job: make the right choice easy and the wrong choice unattractive.

A description that works has four parts:

1. **What it does**, concretely, in the domain's own nouns.
2. **When to use it**, naming triggers the user will actually produce — file
   extensions, tool names, error messages, task phrasings.
3. **What it is not for**, naming the neighbouring skill that covers that.
4. **No hedging.** "Helps with various hardware tasks" competes with nothing
   and wins nothing.

```yaml
# Too vague: never fires, or fires on everything.
description: Helps with Verilog code.

# Works: concrete triggers, an explicit boundary.
description: >
  Write and review synthesisable Verilog and SystemVerilog RTL... Use when
  writing, reviewing or debugging .v/.sv files, when a module has to pass
  synthesis, or when Yosys, Verilator or Vivado reports an elaboration error.
  Not for testbench structure, which belongs to rtl-testbench-discipline.
```

Write the description first and the discovery evals immediately after. Writing
the evals second, from the description, catches the case where the description
sounds right and selects nothing.

A YAML detail that costs a debugging session: an unquoted description
containing `: ` breaks the frontmatter parse. Either quote the string or
rephrase without the colon.

## Voice

Explain why, rather than issuing imperatives. A model that knows *why*
non-blocking assignments belong in clocked blocks handles the case you did not
anticipate; a model told "ALWAYS use non-blocking" follows the rule into
situations where it does not apply and has nothing to fall back on.

All-caps imperatives (`MUST`, `NEVER`, `ALWAYS`) are a signal that a reason
went missing, which is why the validator rejects them. Rewrite `NEVER use
blocking assignments in always_ff` as "use `<=` in clocked blocks; `=` there
creates a simulation race whose outcome depends on statement order".

Write for a competent practitioner who has not done this particular thing
before. Not a tutorial, not a reference manual: the decisions, the traps, and
where to look for more.

## The honest-limits section

Every skill in this repo ends with one, saying what its scripts cannot see and
what a clean result does not prove. It is not a disclaimer. It is the section
that keeps a model from reporting a heuristic pass as a verification result,
which is the difference between a useful assistant and a confident one.

## Order of writing

1. The description.
2. The discovery evals, from the description.
3. The usefulness cases, from real mistakes you have seen.
4. The scripts, where the work is deterministic.
5. `SKILL.md`, aimed at the cases.
6. `references/`, for what did not fit.
7. Run the evals. If the skill does not beat its own baseline, it is not ready.

Writing the evals before the body is the part that changes the outcome. A body
written first tends to document what the author knows; a body written against
failing cases tends to fix what the model gets wrong.

## Distribution

A plugin bundles skills; a marketplace is a repository with
`.claude-plugin/marketplace.json` that distributes plugins. Users add the
marketplace and install the plugin, and the skills become available for
selection by description.

Skills are not MCP servers and not subagents. MCP exposes tools and data; a
skill tells the model how to use capabilities it already has. A subagent gets
its own context window and role; a skill loads into the current one. If the
thing you are building needs an API connection, that is MCP. If it needs
judgement about how to do a task well, that is a skill.
