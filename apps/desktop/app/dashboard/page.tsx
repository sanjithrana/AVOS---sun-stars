import { redirect } from "next/navigation";

// The Dashboard became two tabs: Facts (this pipeline) and Animations.
export default function DashboardRedirect() {
  redirect("/facts");
}
