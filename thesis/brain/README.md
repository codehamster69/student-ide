# The brain

A dated, append-only log of everything that happens on the Student IDE
thesis project: events, decisions, results, plans and problems, each with
the reasoning behind it. When it's time to write the mid-sem report, the
final thesis, or a paper, this is where the story comes from.

- Entries live in [`entries/`](entries/), one file per entry, named
  `YYYY-MM-DD-NN-short-slug.md` (NN orders entries on the same day), so they sort chronologically and parallel
  PRs never conflict.
- Use [`TEMPLATE.md`](TEMPLATE.md).
- Never rewrite an old entry's substance. If something changes, add a new
  entry with `supersedes:` pointing at the old one.
- `thesis-chapter` tells the writer where the material belongs (see
  `../latex/chapters/`).

Quick read of the whole log:

```
cat thesis/brain/entries/*.md
```
