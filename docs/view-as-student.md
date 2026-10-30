# View as student

Teachers and admins can open the student side to see what students see.

**Where:** the **View as student** link in the teacher area's header
(`#/student`). A bar at the bottom keeps the mode visible, with **Back to Teach**.

**What you see:** your own and shared labs (admins: every lab), open and
draft ones (drafts are marked "students can't see it yet"), the learning lab
and the practice tasks. Run, Check, Reset, tabs and resume work as for a
student. There is no consent screen: staff are not study participants.

**What is kept out:** the server marks these sessions `context = 'preview'`
(see `auth.previewer`). They never reach baselines, the detector, review, the
live view, lab progress or session counts, or the research export, and they
never block deleting a lab or question (they are deleted with it).
Competitions can't be joined or entered from student view, so staff never
appear on a class board.

**Who counts as staff:** with Google sign-in, an account whose role is teacher
or admin, acting under its own staff id. In dev mode, requests that carry the
admin token (the teacher area's token, sent by the student pages only in
student view). Students can never mark their own sessions as previews.
