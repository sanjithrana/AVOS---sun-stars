"use client";

import { useParams } from "next/navigation";
import { Project } from "@/components/reelmimic/Project";
import { RmRoot } from "@/components/reelmimic/Shell";

export default function AnimationProjectPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RmRoot>
      <Project key={id} id={id} />
    </RmRoot>
  );
}
