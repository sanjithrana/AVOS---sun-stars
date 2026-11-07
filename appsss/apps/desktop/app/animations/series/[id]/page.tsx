"use client";

import { useParams } from "next/navigation";
import { SeriesPage } from "@/components/series/SeriesPage";

export default function OneSeriesPage() {
  const { id } = useParams<{ id: string }>();
  return <SeriesPage key={id} id={id} />;
}
