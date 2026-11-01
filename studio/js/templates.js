// Video templates. Each one only sets defaults; every value can be changed per scene.
// Durations are in seconds. "pace" scales the voice speed and the words-per-second estimate.

export const TEMPLATES = {
  inspiration: {
    id: "inspiration",
    onScreen: "line", // "line" = the spoken line is the big on-screen text; "title" = scene title + subtitles
    name: "Inspiration",
    blurb: "Short, uplifting lines over calm visuals.",
    icon: "✦",
    structure: ["Hook", "Belief", "Story", "Turning point", "Call to action"],
    sceneSeconds: { min: 4, default: 6, max: 14 },
    titleCard: { seconds: 3, text: "{title}" },
    endCard: { seconds: 3, text: "{title}" },
    text: { font: "600 64px 'Segoe UI', Arial, sans-serif", align: "center", position: "middle", color: "#ffffff", shadow: true, caps: false },
    subtitles: { position: "bottom", size: 0.042 },
    transition: { type: "fade", seconds: 0.8 },
    kenBurns: { zoom: 0.08, pan: 0.03 },
    background: { color: "#152238" },
    music: { mood: "Warm piano / ambient", volume: 0.28 },
    voice: { pace: 0.92, pauseAfterScene: 0.6 },
    sample: "Every great product starts with a question.\n\nWhat if cost was part of the design, not an afterthought?\n\nOur engineers asked that question every single day.\n\nAnd the answer changed how we build.\n\nDesign with the full cost in view. Start today.",
  },
  trailer: {
    id: "trailer",
    onScreen: "line", // "line" = the spoken line is the big on-screen text; "title" = scene title + subtitles
    name: "Film trailer",
    blurb: "Punchy cuts, bold titles, dramatic pauses.",
    icon: "▶",
    structure: ["Cold open", "Rising tension", "Reveal", "Climax", "Title"],
    sceneSeconds: { min: 2, default: 3.5, max: 8 },
    titleCard: { seconds: 2.5, text: "{title}" },
    endCard: { seconds: 3, text: "Coming soon" },
    text: { font: "800 78px 'Segoe UI', Arial, sans-serif", align: "center", position: "middle", color: "#ffffff", shadow: true, caps: true },
    subtitles: { position: "bottom", size: 0.04 },
    transition: { type: "zoom", seconds: 0.35 },
    kenBurns: { zoom: 0.14, pan: 0.05 },
    background: { color: "#0e1a2c" },
    music: { mood: "Cinematic percussion / tension", volume: 0.4 },
    voice: { pace: 0.88, pauseAfterScene: 0.35 },
    sample: "In a world of rising costs.\n\nOne team refused to guess.\n\nEvery part. Every price. Every decision.\n\nThis time, the numbers tell the story.\n\nDesign to Cost.",
  },
  explainer: {
    id: "explainer",
    onScreen: "title", // "line" = the spoken line is the big on-screen text; "title" = scene title + subtitles
    name: "Explainer",
    blurb: "Clear steps, steady pace, readable on-screen text.",
    icon: "?",
    structure: ["Problem", "Why it matters", "How it works", "Example", "Summary"],
    sceneSeconds: { min: 5, default: 9, max: 30 },
    titleCard: { seconds: 3, text: "{title}" },
    endCard: { seconds: 3, text: "Thanks for watching" },
    text: { font: "700 54px 'Segoe UI', Arial, sans-serif", align: "left", position: "top", color: "#ffffff", shadow: false, caps: false },
    subtitles: { position: "bottom", size: 0.038 },
    transition: { type: "slide", seconds: 0.6 },
    kenBurns: { zoom: 0.05, pan: 0.02 },
    background: { color: "#1f5fa8" },
    music: { mood: "Light corporate", volume: 0.18 },
    voice: { pace: 1.0, pauseAfterScene: 0.5 },
    sample: "# The problem\nMaterial prices change every month, and part costs drift without anyone noticing.\n\n# How it works\nThe tool links commodity indices and exchange rates to each part in the bill of materials.\n\n# An example\nWhen steel rises eight percent, you see the effect on every product within seconds.\n\n# Summary\nOne view of the full cost, always up to date.",
  },
  product: {
    id: "product",
    onScreen: "title", // "line" = the spoken line is the big on-screen text; "title" = scene title + subtitles
    name: "Product video",
    blurb: "Feature by feature, with screenshots or clips.",
    icon: "◆",
    structure: ["Intro", "Feature 1", "Feature 2", "Feature 3", "Pricing / CTA"],
    sceneSeconds: { min: 4, default: 7, max: 20 },
    titleCard: { seconds: 3, text: "{title}" },
    endCard: { seconds: 3.5, text: "Book a demo" },
    text: { font: "700 58px 'Segoe UI', Arial, sans-serif", align: "left", position: "bottom", color: "#ffffff", shadow: true, caps: false },
    subtitles: { position: "bottom", size: 0.038 },
    transition: { type: "slide", seconds: 0.5 },
    kenBurns: { zoom: 0.06, pan: 0.03 },
    background: { color: "#152238" },
    music: { mood: "Upbeat electronic", volume: 0.22 },
    voice: { pace: 1.05, pauseAfterScene: 0.4 },
    sample: "# Meet Design to Cost\nOne place for every cost decision.\n\n# Part cost breakdown\nSee every part's cost, broken down by material, process and overhead.\n\n# Live commodity prices\nTrack commodity and currency changes automatically.\n\n# Supplier comparison\nCompare suppliers side by side and spot savings.\n\n# Book a demo\nBook your demo today.",
  },
  documentary: {
    id: "documentary",
    onScreen: "title", // "line" = the spoken line is the big on-screen text; "title" = scene title + subtitles
    name: "Audio documentary",
    blurb: "Voice first. Long, calm narration; exports audio too.",
    icon: "♪",
    structure: ["Opening", "Background", "Interview / evidence", "Reflection", "Closing"],
    sceneSeconds: { min: 8, default: 20, max: 120 },
    titleCard: { seconds: 4, text: "{title}" },
    endCard: { seconds: 4, text: "{title}" },
    text: { font: "500 46px Georgia, 'Times New Roman', serif", align: "center", position: "middle", color: "#eef4fb", shadow: false, caps: false },
    subtitles: { position: "bottom", size: 0.036 },
    transition: { type: "fade", seconds: 1.5 },
    kenBurns: { zoom: 0.04, pan: 0.015 },
    background: { color: "#0e1a2c" },
    music: { mood: "Soft strings / drone", volume: 0.15 },
    voice: { pace: 0.9, pauseAfterScene: 1.2 },
    audioOnly: true,
    sample: "# The workshop\nIt began in a small workshop, where every price was written in a notebook.\n\n# From paper to system\nOver the years, the notebooks became spreadsheets, and the spreadsheets became a system.\n\n# The long nights\nThe people who built it remember the long nights of reconciling numbers that never matched.\n\n# Today\nToday, the numbers match. But the questions behind them are the same: what does it really cost, and why?",
  },
};

export const TEMPLATE_IDS = Object.keys(TEMPLATES);

export function getTemplate(id) {
  return TEMPLATES[id] || TEMPLATES.explainer;
}
