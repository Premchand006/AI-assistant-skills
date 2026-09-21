## What this changes

<!-- One or two sentences. If it adds a skill, name the mistake the skill
     exists to prevent. -->

## Checks

<!-- Paste the output, or tick after running them. CI runs the same four. -->

- [ ] `python3 tools/validate_skills.py --strict`
- [ ] `python3 tools/test_scripts.py`
- [ ] `python3 tools/smoke_imports.py`
- [ ] `shellcheck -S warning skills/*/scripts/*.sh` (if shell scripts changed)

## For a new or changed skill

- [ ] The description says what it does, when to use it, and what it is **not**
      for, naming the skill that covers that instead
- [ ] At least three usefulness cases where the skill-off answer is plausibly
      wrong — a case both modes pass measures nothing
- [ ] Adversarial discovery prompts that share vocabulary but belong elsewhere
- [ ] An honest-limits section naming what the scripts cannot see
- [ ] Any new script has a fixture and a case in `tools/test_scripts.py`

## Evidence

<!-- If you recorded eval transcripts, say which model and version produced
     them. Results do not transfer between models. If you did not record any,
     say so — maintainers can. -->

## Attribution

- [ ] Nothing here is copied from another repository's skill text, references
      or scripts
