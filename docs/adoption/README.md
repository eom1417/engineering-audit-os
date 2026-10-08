# Adopt before build: scouting records

The owner's rule (EAOS v2, 2026-10-08): before any code is written for a new capability, a scouting record says
which existing projects could do it, under which licence, how alive they are, and what was decided. EAOS writes code
only where the record shows nothing adequate exists, or for the thin glue that wires an adopted project in.

The source of the candidates is `eaos-dev/planning/studio-v2/E-adopt-before-build.md` (lens E of the v2 plan); a
record here narrows it to one task and pins what is adopted.

## The format of a record

One file per task, `docs/adoption/<task>.md`. Each capability is a `## ` section that holds, in this order:

- `**Candidates**`: a table with every candidate looked at, its licence, the version and date it was checked at,
  and its maintenance (last release, open source health).
- `**Decision**`: adopt, build (with the reason no candidate fits) or reject, in one paragraph.
- `**Pinned**`: the packages adopted, each as `` `name@version` ``, or `none`.

The licence policy is `docs/TOOLCHAIN.md` §2: a library bundled into the Studio is embedded, so only MIT, BSD, ISC,
Apache-2.0, CC0, OFL (fonts) and file-level copyleft left unmodified (MPL-2.0, EPL-2.0) are accepted.

## How the plan measures it (indicator W2)

`python tools/north_star.py measure --only W2` reads every record here. W2 is the share of the Studio's packages
(`studio/package.json`, dependencies and dev dependencies) that a record pins with all three parts present and that
was committed no later than the commit that first added that package to `studio/package.json`. A package added
without a record, or a record written after the package came in, lowers it.

## Records

| Task | Record |
|---|---|
| NS37.T1 design system and shell | [ns37-t1-studio-shell.md](ns37-t1-studio-shell.md) |
| NS37.T1 finishing: bundle locales, one screen gate | [ns37-t1-finish.md](ns37-t1-finish.md) |
