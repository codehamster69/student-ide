import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Logo } from "../ui";
import { href } from "../routes";
import { GuideIndex, GuideReader } from "./GuideView";
import type { Audience } from "./content";

/**
 * The public guide at #/help[/<audience>/<slug>]: readable without signing in,
 * linked from the sign-in screen and the desktop app's Help menu.
 */

function parse(): { audience?: Audience; slug?: string } {
  const m = location.hash.match(/^#\/help(?:\/(student|teacher)(?:\/([\w-]+))?)?/);
  return { audience: m?.[1] as Audience | undefined, slug: m?.[2] };
}

export function HelpPage() {
  const [at, setAt] = useState(parse);
  useEffect(() => {
    const on = () => setAt(parse());
    window.addEventListener("hashchange", on);
    document.title = "Guide · Student IDE";
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg/85 px-4 backdrop-blur-md sm:px-6">
        <a href={href.help()} className="rounded-lg"><Logo subtitle="Guide" /></a>
        <a href="#/" className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-medium text-muted hover:bg-surface-2 hover:text-text">
          <ArrowLeft className="size-3.5" />Back to Student IDE
        </a>
      </header>
      {at.audience ? <GuideReader audience={at.audience} slug={at.slug} nav={{ href: href.help }} /> : <GuideIndex nav={{ href: href.help }} />}
    </div>
  );
}
