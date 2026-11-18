import { SourceReviewView } from "./source-review-view";

/**
 * Server shell. Dynamic now that proposals come from the API per guest session
 * rather than from local fixtures.
 */
export const instant = false;

export default async function SourceReviewPage({
  params,
}: PageProps<"/cases/[id]/review">) {
  const { id } = await params;
  return <SourceReviewView id={id} />;
}
