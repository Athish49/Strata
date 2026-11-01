import { VerticalView } from "@/components/documents/board/VerticalView";

// `notFound()` only works in Server Components/Server Functions/Route Handlers, and the
// verticals list now lives in the DB (task 3.7), not a static import, so the slug can't be
// validated here without a server-side fetch -- which would risk a false 404 on a real
// vertical if the backend is cold-starting (Render free tier). VerticalView (client) does
// the validation instead, once useVerticals() resolves, and renders its own not-found state.
export default async function Page({ params }: { params: Promise<{ vertical: string }> }) {
  const { vertical } = await params;
  return <VerticalView slug={vertical} />;
}
