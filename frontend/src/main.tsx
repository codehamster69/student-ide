import { lazy, Suspense, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./ui/tokens.css";

// The teacher area (#/teach labs, #/live class view, #/review timeline) is for teachers and researchers. It is loaded
// on demand so the student editor bundle stays as small as before.
const ReviewApp = lazy(() => import("./review/ReviewApp").then((m) => ({ default: m.ReviewApp })));

const isTeacher = () => /^#\/(review|teach|live)/.test(location.hash);
// "View as student" (#/student) is decided when the student app starts, so entering it remounts that app
const isPreview = () => location.hash.startsWith("#/student");

function Root() {
  const [review, setReview] = useState(() => isTeacher());
  const [preview, setPreview] = useState(() => isPreview());
  useEffect(() => {
    const on = () => { setReview(isTeacher()); setPreview(isPreview()); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return review ? <Suspense fallback={null}><ReviewApp /></Suspense> : <App key={preview ? "preview" : "student"} />;
}

// No <StrictMode>: its double-invoked effects would open the editor twice and
// log a duplicate start snapshot into the research data.
createRoot(document.getElementById("app")!).render(<Root />);
