import { lazy, Suspense, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { DesktopUpdate } from "./screens/DesktopUpdate";
import { DESKTOP_SIGNIN } from "./desktop";
import { DOWNLOAD_PAGE } from "./download";
import "./ui/tokens.css";

// The teacher area (#/teach labs, #/live class view, #/review timeline) is for teachers and researchers. It is loaded
// on demand so the student editor bundle stays as small as before.
const DesktopSignIn = lazy(() => import("./screens/DesktopSignIn").then((m) => ({ default: m.DesktopSignIn })));

const DownloadPage = lazy(() => import("./screens/Download").then((m) => ({ default: m.DownloadPage })));

// the public guide (#/help), readable before signing in and opened by the desktop app's Help menu
const HelpPage = lazy(() => import("./guide/HelpPage").then((m) => ({ default: m.HelpPage })));
const isHelp = () => location.hash.startsWith("#/help");

const ReviewApp = lazy(() => import("./review/ReviewApp").then((m) => ({ default: m.ReviewApp })));

const isTeacher = () => /^#\/(review|teach|live|sandbox|guide)/.test(location.hash);
// "View as student" (#/student) is decided when the student app starts, so entering it remounts that app
const isPreview = () => location.hash.startsWith("#/student");
// the desktop app's sign-in page, opened in the system browser (docs/desktop.md)
const isDesktopSignIn = () => location.hash.startsWith(DESKTOP_SIGNIN);
// the public desktop download page, shareable before any lab exists
const isDownload = () => location.hash.startsWith(DOWNLOAD_PAGE);

function Root() {
  const [review, setReview] = useState(() => isTeacher());
  const [preview, setPreview] = useState(() => isPreview());
  const [download, setDownload] = useState(() => isDownload());
  const [help, setHelp] = useState(() => isHelp());
  useEffect(() => {
    const on = () => { setReview(isTeacher()); setPreview(isPreview()); setDownload(isDownload()); setHelp(isHelp()); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  if (help) return <Suspense fallback={null}><HelpPage /></Suspense>;
  if (download) return <Suspense fallback={null}><DownloadPage /></Suspense>;
  if (isDesktopSignIn()) return <Suspense fallback={null}><DesktopSignIn /></Suspense>;
  // staff areas get the desktop update card too (the student app places its own)
  return review ? <Suspense fallback={null}><ReviewApp /><DesktopUpdate hidden={false} /></Suspense> : <App key={preview ? "preview" : "student"} />;
}

// No <StrictMode>: its double-invoked effects would open the editor twice and
// log a duplicate start snapshot into the research data.
createRoot(document.getElementById("app")!).render(<Root />);
