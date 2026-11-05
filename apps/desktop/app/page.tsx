import { redirect } from "next/navigation";

// The old home page was a static mockup with hardcoded data (fake crew,
// fake storyboard, non-working buttons). The real app starts at the
// Facts tab.
export default function Home() {
  redirect("/facts");
}
