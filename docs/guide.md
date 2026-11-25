# Guides and help centre

In-app documentation for students and teachers, written as Markdown and rendered by the app.

## Where it lives

| piece | file |
|---|---|
| Pages | `frontend/src/guide/pages/<student\|teacher>/<slug>.md`, front matter `title`, `summary`, `order`, `keywords` |
| Loader, search, link resolution | `frontend/src/guide/content.ts` (bundled with `import.meta.glob`, no server call) |
| Renderer | `frontend/src/guide/GuideMarkdown.tsx`: React elements, never HTML; `##`/`###`, lists, tables, code, `>` notes, links |
| Index and reader | `frontend/src/guide/GuideView.tsx` (page list, search, On this page, previous/next) |
| Public page | `frontend/src/guide/HelpPage.tsx` at `#/help[/<audience>/<slug>]` |

## Where people find it

- **Teachers:** Guide in the sidebar (`#/guide`, `#/guide/<audience>/<slug>`, in `routes.ts`); the top bar's
  **Help** button opens the guide page for the screen you are on (`helpFor()` in `review/ReviewApp.tsx`);
  guide pages are in Ctrl+K.
- **Students:** the Guide tab in the app bar (student guide only, loaded on demand); "How Scribelab works" on
  the sign-in screen opens `#/help/student/getting-started`.
- **Desktop app:** Help menu → the public guide in its own window (`docs/desktop.md`).

## Writing a page

Plain second person, short sections, numbered steps only for real sequences. Facts come from the code and
`docs/*.md`. Link another page with its bare slug, `[Attendance](attendance)`, which resolves in the same
audience; `teacher/live-view` crosses over. Keep the consent wording out of the guides (refer to it), and keep
the framing that a flag only leads to a conversation. `frontend/e2e/guide.mjs` checks that every link resolves.
