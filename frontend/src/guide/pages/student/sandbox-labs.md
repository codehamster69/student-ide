---
title: Sandbox Labs
summary: Labs that run on your own computer in the desktop app, with a real Linux terminal, local checks and graded submissions.
order: 6
keywords: [sandbox, desktop app, install, terminal, workspace, submit, grading, docker, linux, download, vim, due]
---

Sandbox Labs are real-world labs: a Linux environment with the tools your subject needs, a terminal, and assignments with tests. They run **on your own computer** in the Scribelab desktop app. The website only lists them.

## Get the app

Open the download page (the **Get the app** link on the home page's Sandbox labs section) and pick the installer for your computer: Windows 10 (2004 or later) or 11, macOS 13 or later, or Linux. You need about 4 GB free; the first launch downloads the lab environment.

You do not install Docker yourself. The app sets up a private engine for Scribelab alone:

- **Windows:** a small Linux environment (WSL2). If WSL2 is off, one administrator prompt turns it on, and a restart may be needed once.
- **macOS:** a small virtual machine, no admin rights.
- **Linux:** uses Podman if you have it, or installs it.

If setup stops, the window says what to fix in plain words (for example: virtualization is off in the BIOS, or disk space is low). Running setup again carries on where it stopped. In a lab room, IT can prepare PCs once; ask your teacher.

The app keeps itself up to date, and updates are required: when a new version is out it installs as soon as you are not in a lab (it never restarts in the middle of one), then opens where you were. Until then you can finish what is open but not start something new; **Update now** on the card does it straight away. A lab that needs a newer version says **Update the app to open**.

## Open a lab

Sign in to the app with your college account. Your Sandbox labs appear on the home page grouped by subject. Each card shows if the lab is assessed, its network setting (**Internet on**, **Package sites only**, or **No internet**) and the due time. Press a card to open it. The first open shows steps like *Getting the lab environment ready… → Starting your Linux instance… → Bringing back your files…*.

The first time, you also see a short extra consent about the terminal. See [What we record](what-we-record).

## The workspace

- **Assignment rail.** Numbered chips along the top show each assignment's state. `Ctrl + 1…9` (`⌘` on a Mac) switches assignment. Each keeps its own editor and shell.
- **Files and editor.** Your assignment folder, with starter files. Edits save automatically a moment after you stop typing.
- **Terminal.** A real shell in the assignment folder. After `exit`, press **New shell**. File lists refresh when a command ends.
- **Right panel.** **Statement**, **Output**, **Tests**, **Grade** and **Input**.

Your starter files are written only when the folder does not exist yet, so a teacher's later update never overwrites your work. Your folder is backed up to the server, so you can pick up on another computer. If a copy conflicts, the app keeps both and tells you.

## Run, Check, Submit

- **Run** (`Ctrl + Enter`) runs the assignment's command.
- **Check** tries the tests you can see, on your machine. A note says how many more tests your teacher checks on submission.
- **Submit** asks you to confirm, uploads your folder and starts grading. The result appears under **Grade** within moments: how many tests passed, each visible test in full, and for hidden tests only the name and pass or fail.

You can submit again until the due time; the latest submission counts. After the due time the lab may be closed, or accept late work with a penalty, depending on your teacher's late policy. The lab's page says which. A submission after a lab has closed is refused with a message; your work is still saved.

Grading uses the lab's own environment, not packages you installed yourself, as any autograder does.

## If the connection drops

Your work stays saved on your computer and you can keep going for 5 minutes. After that editing pauses until the connection is back. A gap is never treated as a problem.

## Vim

Turn on the **Vim** switch next to the editor to use Vim keys. See [Shortcuts](shortcuts).
