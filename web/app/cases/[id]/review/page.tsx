import { notFound } from "next/navigation";
import { SOURCE_REVIEW, getSourceReview } from "@/lib/source-review-fixtures";
import { SourceReviewView } from "./source-review-view";

/**
 * Server shell. Static while the proposals are mock fixtures; becomes a dynamic
 * route when the extraction endpoint lands (see the note in ../page.tsx).
 */
export function generateStaticParams() {
  return Object.keys(SOURCE_REVIEW).map((id) => ({ id }));
}

export default async function SourceReviewPage({
  params,
}: PageProps<"/cases/[id]/review">) {
  const { id } = await params;
  if (!getSourceReview(id)) notFound();
  return <SourceReviewView id={id} />;
}
