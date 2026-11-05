"use client";

import { FilmHome } from "@/components/films/FilmHome";

// Not inside the Animations tab's ".rm" scope: Films use AVOS's own design system (Tailwind + ui components).
export default function FilmsPage() {
  return <FilmHome />;
}
