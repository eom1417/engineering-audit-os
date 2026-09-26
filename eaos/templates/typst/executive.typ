// EXECUTIVE.pdf: one page for the person who decides. Every word and number comes from executive.json,
// which eaos/compose/pdf.py builds from the report's own records; this template adds layout only.
#let data = json("executive.json")
#let ar = data.language == "ar"
#set document(title: data.title)
#set page(paper: "a4", margin: (x: 1.5cm, y: 1.3cm),
  footer: align(center, text(size: 7.5pt, fill: luma(110), data.footer)))
#set text(font: ("Noto Naskh Arabic", "Noto Sans", "DejaVu Sans"), size: 9.5pt, lang: data.language,
  dir: if ar { rtl } else { ltr })
#set par(leading: 0.55em, spacing: 0.7em)
#show heading.where(level: 2): it => block(above: 0.9em, below: 0.45em,
  text(size: 11pt, weight: "bold", fill: rgb("#1e3a8a"), it.body))
#let cell(body) = text(size: 8.5pt, body)

#text(size: 16pt, weight: "bold", data.title)
#v(-0.3em)
#text(size: 8.5pt, fill: luma(90), data.subtitle)

#block(fill: rgb("#eff6ff"), stroke: (left: 3pt + rgb("#1d4ed8")), inset: 8pt, width: 100%)[
  #text(weight: "bold", data.labels.decision): #data.decision
]

== #data.labels.numbers
#table(columns: (auto, 1fr, auto), stroke: 0.4pt + luma(200), inset: 5pt,
  table.header(..data.labels.number_columns.map(h => text(weight: "bold", size: 8.5pt, h))),
  ..data.numbers.map(n => (text(weight: "bold", size: 11pt, n.value), cell(n.label), cell(raw(n.source)))).flatten())

== #data.labels.risks
#table(columns: (auto, auto, 1fr), stroke: 0.4pt + luma(200), inset: 5pt,
  table.header(..data.labels.risk_columns.map(h => text(weight: "bold", size: 8.5pt, h))),
  ..data.risks.map(r => (cell(raw(r.id)), cell(r.severity), cell(r.title))).flatten())

== #data.labels.milestones
#table(columns: (auto, auto, 1fr, auto), stroke: 0.4pt + luma(200), inset: 5pt,
  table.header(..data.labels.milestone_columns.map(h => text(weight: "bold", size: 8.5pt, h))),
  ..data.milestones.map(m => (cell(m.id), cell(raw(m.name)), cell(m.goal), cell(m.cards))).flatten())
