import { CaseDetailView } from "./case-detail-view";

/**
 * Server shell for case detail.
 *
 * Now a dynamic route (roadmap C4): the case set comes from the API per guest
 * session, so enumerating it with generateStaticParams is no longer honest.
 * `instant = false` makes this a blocking route, which Cache Components
 * requires for a param read outside Suspense.
 */
export const instant = false;

export default async function CaseDetailPage({
  params,
}: PageProps<"/cases/[id]">) {
  const { id } = await params;
  // Existence is decided by the API, not by a local fixture: an unknown id
  // returns a structured 404 that the view renders.
  return <CaseDetailView id={id} />;
}
