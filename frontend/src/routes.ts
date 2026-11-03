/**
 * Every teacher-area page, in one table. Links use the `href` builders and the
 * app reads the hash with `parseRoute`, so the URL scheme stays the same everywhere:
 *
 *   #/<area>[/<collection>[/<id>[/<view>]]]
 *
 * Areas are what the top tabs show (teach, live, review); collections are plural
 * nouns; an item is /<collection>/<id> and a view of it one more segment.
 *
 *   #/teach                          Labs                 #/teach/labs/<id>              one lab
 *   #/teach/labs/<id>/attendance     its attendance       #/teach/labs/<id>/board        competition leaderboard
 *   #/teach/labs/<id>/similar        similar submissions  #/teach/subjects[/<slug>]      subjects
 *   #/teach/setup                    Getting started      #/teach/people                 accounts (admins)
 *   #/live                           open labs            #/live/labs/<id>               class view
 *   #/live/sessions/<id>             one student's editor
 *   #/review                         lab sessions         #/review/labs/<id>[/<day>]     one lab session
 *   #/review/sessions                every session        #/review/sessions/<id>         one session's timeline
 *   #/student                        View as student (the student app, under a staff account)
 *
 * Older links (#/teach/l/<id>, #/teach/c/<id>, #/teach/similar/<id>, #/live/l/<id>,
 * #/live/s/<id>, #/review/l/<id>, #/review/s/<id>, #/review/all) still open the
 * same page and are rewritten to the scheme above.
 */

export type Route =
  | { name: "labs" } | { name: "lab"; id: string; view?: "attendance" } | { name: "board"; id: string } | { name: "similar"; id: string }
  | { name: "subjects" } | { name: "subject"; slug: string } | { name: "setup" } | { name: "people" }
  | { name: "live" } | { name: "live-lab"; id: string } | { name: "live-session"; id: string }
  | { name: "overview" } | { name: "review-lab"; id: string; day?: string } | { name: "review-all" } | { name: "session"; id: string };

export type Area = "teach" | "live" | "review";

const ID = "([A-Za-z0-9_-]+)";
const DAY = "(\\d{4}-\\d{2}-\\d{2})";

/** pattern (after "#/"), what it means; first match wins, so longer paths come first. */
const TABLE: [RegExp, (m: RegExpMatchArray) => Route][] = [
  [re(`teach/labs/${ID}/attendance`), (m) => ({ name: "lab", id: m[1], view: "attendance" })],
  [re(`teach/labs/${ID}/board`), (m) => ({ name: "board", id: m[1] })],
  [re(`teach/labs/${ID}/similar`), (m) => ({ name: "similar", id: m[1] })],
  [re(`teach/labs/${ID}`), (m) => ({ name: "lab", id: m[1] })],
  [re("teach/labs"), () => ({ name: "labs" })],
  [re("teach/subjects/([^/]+)"), (m) => ({ name: "subject", slug: decodeURIComponent(m[1]) })],
  [re("teach/subjects"), () => ({ name: "subjects" })],
  [re("teach/setup"), () => ({ name: "setup" })],
  [re("teach/people"), () => ({ name: "people" })],
  [re(`live/labs/${ID}`), (m) => ({ name: "live-lab", id: m[1] })],
  [re(`live/sessions/${ID}`), (m) => ({ name: "live-session", id: m[1] })],
  [re(`review/labs/${ID}(?:/${DAY})?`), (m) => ({ name: "review-lab", id: m[1], day: m[2] })],
  [re(`review/sessions/${ID}`), (m) => ({ name: "session", id: m[1] })],
  [re("review/sessions"), () => ({ name: "review-all" })],
  // older links
  [re(`teach/l/${ID}`), (m) => ({ name: "lab", id: m[1] })],
  [re(`teach/c/${ID}`), (m) => ({ name: "board", id: m[1] })],
  [re(`teach/similar/${ID}`), (m) => ({ name: "similar", id: m[1] })],
  [re(`live/l/${ID}`), (m) => ({ name: "live-lab", id: m[1] })],
  [re(`live/s/${ID}`), (m) => ({ name: "live-session", id: m[1] })],
  [re(`review/l/${ID}(?:/${DAY})?`), (m) => ({ name: "review-lab", id: m[1], day: m[2] })],
  [re(`review/s/${ID}`), (m) => ({ name: "session", id: m[1] })],
  [re("review/all"), () => ({ name: "review-all" })],
  [re("teach"), () => ({ name: "labs" })],
  [re("live"), () => ({ name: "live" })],
];

function re(path: string) {
  return new RegExp(`^#/${path}/?(?:[?].*)?$`);
}

export function parseRoute(hash = location.hash): Route {
  for (const [pattern, make] of TABLE) {
    const m = hash.match(pattern);
    if (m) return make(m);
  }
  return { name: "overview" };
}

/** The canonical hash for a route (what `href` builds). */
export function routeHash(r: Route): string {
  switch (r.name) {
    case "labs": return href.labs;
    case "lab": return r.view ? href.labAttendance(r.id) : href.lab(r.id);
    case "board": return href.board(r.id);
    case "similar": return href.similar(r.id);
    case "subjects": return href.subjects;
    case "subject": return `#/teach/subjects/${encodeURIComponent(r.slug)}`;
    case "setup": return href.setup;
    case "people": return href.people;
    case "live": return href.live;
    case "live-lab": return href.liveLab(r.id);
    case "live-session": return href.liveSession(r.id);
    case "overview": return href.review;
    case "review-lab": return href.reviewLab(r.id, r.day);
    case "review-all": return href.reviewAll;
    case "session": return href.session(r.id);
  }
}

/** Rewrites an older link in the address bar to the current scheme, without a new history entry. */
export function canonicalize(): void {
  if (!/^#\/(teach|live|review)/.test(location.hash)) return;
  const want = routeHash(parseRoute());
  if (want !== location.hash.replace(/\/$/, "")) history.replaceState(null, "", want);
}

export function areaOf(r: Route): Area {
  if (r.name.startsWith("live")) return "live";
  if (r.name === "overview" || r.name.startsWith("review") || r.name === "session") return "review";
  return "teach";
}

/** "Data Structures" -> "data-structures": a subject's key in #/teach/subjects/<slug>. */
export function subjectSlug(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "no-subject";
}

export const href = {
  labs: "#/teach",
  lab: (id: string) => `#/teach/labs/${id}`,
  labAttendance: (id: string) => `#/teach/labs/${id}/attendance`,
  board: (id: string) => `#/teach/labs/${id}/board`,
  similar: (id: string) => `#/teach/labs/${id}/similar`,
  subjects: "#/teach/subjects",
  subject: (name: string) => `#/teach/subjects/${encodeURIComponent(subjectSlug(name))}`,
  setup: "#/teach/setup",
  people: "#/teach/people",
  live: "#/live",
  liveLab: (id: string) => `#/live/labs/${id}`,
  liveSession: (id: string | null) => `#/live/sessions/${id}`,
  review: "#/review",
  reviewLab: (id: string, day?: string) => (day ? `#/review/labs/${id}/${day}` : `#/review/labs/${id}`),
  reviewAll: "#/review/sessions",
  session: (id: string | null) => `#/review/sessions/${id}`,
  student: "#/student",
} as const;

export const go = (hash: string) => { location.hash = hash; };
