import { redirect } from "next/navigation";

// The Dashboard became two tabs: Explainer and Animations.
export default function DashboardRedirect() {
  redirect("/explainer");
}
