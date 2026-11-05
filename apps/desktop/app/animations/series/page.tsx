"use client";

import { SeriesHome } from "@/components/series/SeriesHome";

// Not inside the Animations tab's ".rm" scope: Series uses AVOS's own design system (Tailwind + ui components).
export default function SeriesListPage() {
  return <SeriesHome />;
}
