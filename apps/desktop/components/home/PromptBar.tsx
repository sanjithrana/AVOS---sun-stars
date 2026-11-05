"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ArrowUp, Loader2 } from "lucide-react";
import { explainer } from "@/lib/explainer";
import { stickman } from "@/lib/stickman";

type Kind = "explainer" | "stickman" | "animation";
const KINDS: [Kind, string, string][] = [
  ["explainer", "Explainer", "Describe the idea or question the video should explain…"],
  ["stickman", "Stickman history", "Name a historical event, e.g. the night the Titanic hit the iceberg…"],
  ["animation", "Animation", "Describe the film or episode you want to make…"],
];
const EXAMPLES: Record<Kind, string[]> = {
  explainer: ["What happens if you drop a magnet down a copper pipe?", "Why can a straw go through a potato?", "How does a plane stay in the air?"],
  stickman: ["The night the Titanic hit the iceberg", "Apollo 13: the oxygen tank explodes", "The fall of the Berlin Wall"],
  animation: ["A grumpy cat and a cheerful robot share a flat", "A tiny dragon learns to cook"],
};

/** The one box on Home: type, pick what to make, and go. The crew handles every technical setting. */
export function PromptBar() {
  const router = useRouter();
  const [kind, setKind] = useState<Kind>("explainer");
  const [text, setText] = useState("");
  const [seconds, setSeconds] = useState(30);
  const [aspect, setAspect] = useState("9:16");
  const [auto, setAuto] = useState(false);
  const go = useMutation({
    mutationFn: async () => {
      const t = text.trim();
      if (kind === "explainer") return `/explainer/${(await explainer.create({ brief: t, seconds, aspect, auto, research: true })).id}`;
      if (kind === "stickman") return `/stickman/${(await stickman.create({ event: t, aspect, auto })).id}`;
      return "/animations";
    },
    onSuccess: (href) => router.push(href),
  });
  const ready = kind === "animation" || text.trim().length >= 3;
  const placeholder = KINDS.find((k) => k[0] === kind)?.[2];
  return (
    <div className="prompt-bar w-full max-w-3xl text-left" data-testid="home-prompt">
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="What to make">
        {KINDS.map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={kind === k} onClick={() => setKind(k)} data-testid={`make-${k}`}
            className={`rounded-full px-4 py-1.5 text-sm transition-colors ${kind === k ? "bg-[rgba(124,92,255,0.22)] text-foreground" : "text-muted-foreground hover:text-foreground"}`}>{l}</button>
        ))}
      </div>
      <form className="prompt-box mt-3 rounded-[1.75rem] border border-[rgba(170,150,255,0.22)] bg-[rgba(8,6,22,0.94)] p-3"
        onSubmit={(e) => { e.preventDefault(); if (ready && !go.isPending) go.mutate(); }}>
        <label htmlFor="home-idea" className="sr-only">Your idea</label>
        <textarea id="home-idea" value={text} onChange={(e) => setText(e.target.value)} rows={3} placeholder={placeholder} data-testid="home-idea"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && ready) go.mutate(); }}
          className="w-full resize-none !border-0 !bg-transparent px-3 py-2 text-base leading-relaxed !shadow-none outline-none placeholder:text-muted-foreground/70 md:text-lg" />
        <div className="flex flex-wrap items-center gap-2 px-1 pb-1 pt-2">
          {kind === "explainer" && (
            <label className="sr-only" htmlFor="home-len">Length</label>
          )}
          {kind === "explainer" && (
            <select id="home-len" value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} className="h-9 rounded-full px-4 text-sm" data-testid="home-length">
              {[15, 30, 45, 60].map((n) => <option key={n} value={n}>{n} seconds</option>)}
            </select>
          )}
          {kind !== "animation" && (
            <>
              <label className="sr-only" htmlFor="home-shape">Shape</label>
              <select id="home-shape" value={aspect} onChange={(e) => setAspect(e.target.value)} className="h-9 rounded-full px-4 text-sm" data-testid="home-shape">
                <option value="9:16">Vertical 9:16</option>
                <option value="16:9">Wide 16:9</option>
                <option value="1:1">Square 1:1</option>
              </select>
              <div className="inline-flex h-9 items-center rounded-full border border-[rgba(150,130,255,0.3)] p-0.5 text-sm" role="radiogroup" aria-label="How it runs">
                {([[false, "Ask me"], [true, "Automatic"]] as const).map(([v, l]) => (
                  <button key={l} type="button" role="radio" aria-checked={auto === v} onClick={() => setAuto(v)} data-testid={`home-auto-${v ? "on" : "off"}`}
                    className={`h-8 rounded-full px-3 transition-colors ${auto === v ? "bg-[rgba(124,92,255,0.28)] text-foreground" : "text-muted-foreground hover:text-foreground"}`}>{l}</button>
                ))}
              </div>
            </>
          )}
          <button type="submit" disabled={!ready || go.isPending} data-testid="home-generate"
            className="ml-auto inline-flex h-10 items-center gap-2 rounded-full bg-primary px-5 text-sm font-semibold disabled:opacity-40">
            {go.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}{kind === "animation" ? "Open Animation" : "Generate"}
          </button>
        </div>
      </form>
      {go.isError && <p className="mt-2 text-sm text-[#ff8aa0]" role="alert">{(go.error as Error).message}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES[kind].map((x) => (
          <button key={x} type="button" onClick={() => setText(x)} className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground">{x}</button>
        ))}
      </div>
    </div>
  );
}
