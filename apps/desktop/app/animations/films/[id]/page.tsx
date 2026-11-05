"use client";

import { useParams } from "next/navigation";
import { FilmPage } from "@/components/films/FilmPage";

export default function OneFilmPage() {
  const { id } = useParams<{ id: string }>();
  return <FilmPage key={id} id={id} />;
}
