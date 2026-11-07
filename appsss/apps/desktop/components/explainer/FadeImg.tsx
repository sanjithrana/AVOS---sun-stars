"use client";

import { useState } from "react";

/** A picture that fades in once loaded (and shows a soft shimmer until then), so pictures never pop in. */
export function FadeImg({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  const [ok, setOk] = useState(false);
  return (
    <div className={`relative overflow-hidden ${ok ? "" : "animate-pulse bg-muted"}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} loading="lazy" decoding="async" onLoad={() => setOk(true)} onError={() => setOk(true)}
        className={`${className} transition-all duration-500 ease-out ${ok ? "scale-100 opacity-100 blur-0" : "scale-[1.02] opacity-0 blur-sm"}`} />
    </div>
  );
}
