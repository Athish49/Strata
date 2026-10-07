import { redirect } from "next/navigation";

// The marketing landing page is deferred; the root only forwards to the app.
export default function Home() {
  redirect("/app");
}
