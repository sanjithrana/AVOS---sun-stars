import {
  AlertCircle,
  AudioLines,
  Box,
  CheckCircle2,
  Clapperboard,
  FileText,
  Film,
  Hourglass,
  Search,
  XCircle,
  type LucideIcon,
} from "lucide-react";

export interface StatusStyle {
  label: string;
  description: string;
  icon: LucideIcon;
  text: string;
  bg: string;
  border: string;
  bar: string;
  /** Rough pipeline position, for progress bars (0-100). */
  progress: number;
  active: boolean;
}

// One place that defines what every backend ProjectStatus looks like.
export const PROJECT_STATUS: Record<string, StatusStyle> = {
  planning: {
    label: "Ready",
    description: "Created - click Generate to start",
    icon: FileText,
    text: "text-slate-300",
    bg: "bg-slate-500/10",
    border: "border-slate-500/30",
    bar: "bg-slate-500",
    progress: 0,
    active: false,
  },
  researching: {
    label: "Researching",
    description: "Agents are researching and writing the script",
    icon: Search,
    text: "text-blue-300",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    bar: "bg-blue-500",
    progress: 30,
    active: true,
  },
  awaiting_approval: {
    label: "Needs approval",
    description: "Script is waiting for your review",
    icon: Hourglass,
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    bar: "bg-amber-500",
    progress: 55,
    active: true,
  },
  awaiting_review: {
    label: "Review shots",
    description: "Shots passed QA and are waiting for your review before the final video",
    icon: Hourglass,
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    bar: "bg-amber-500",
    progress: 88,
    active: true,
  },
  generating_audio: {
    label: "Generating audio",
    description: "Narration, timestamps and beats in progress",
    icon: AudioLines,
    text: "text-purple-300",
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    bar: "bg-purple-500",
    progress: 60,
    active: true,
  },
  planning_shots: {
    label: "Planning shots",
    description: "ShotSpecs per beat, continuity check and Blender physics proxies",
    icon: Box,
    text: "text-indigo-300",
    bg: "bg-indigo-500/10",
    border: "border-indigo-500/30",
    bar: "bg-indigo-500",
    progress: 70,
    active: true,
  },
  generating_visuals: {
    label: "Generating visuals",
    description: "An AI image and clip for every shot",
    icon: Clapperboard,
    text: "text-pink-300",
    bg: "bg-pink-500/10",
    border: "border-pink-500/30",
    bar: "bg-pink-500",
    progress: 82,
    active: true,
  },
  rendering_video: {
    label: "Rendering video",
    description: "Joining shots, narration and captions into the final MP4",
    icon: Film,
    text: "text-cyan-300",
    bg: "bg-cyan-500/10",
    border: "border-cyan-500/30",
    bar: "bg-cyan-500",
    progress: 94,
    active: true,
  },
  complete: {
    label: "Complete",
    description: "Your video is ready to watch and download",
    icon: CheckCircle2,
    text: "text-green-300",
    bg: "bg-green-500/10",
    border: "border-green-500/30",
    bar: "bg-green-500",
    progress: 100,
    active: false,
  },
  rejected: {
    label: "Script rejected",
    description: "Generate again for a new script",
    icon: XCircle,
    text: "text-orange-300",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    bar: "bg-orange-500",
    progress: 55,
    active: false,
  },
  failed: {
    label: "Failed",
    description: "Something went wrong - you can retry",
    icon: AlertCircle,
    text: "text-red-300",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    bar: "bg-red-500",
    progress: 0,
    active: false,
  },
};

export function statusStyle(status: string): StatusStyle {
  return PROJECT_STATUS[status] ?? PROJECT_STATUS.planning;
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s.toString().padStart(2, "0")}s` : `${s}s`;
}

export function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
