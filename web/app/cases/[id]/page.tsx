import { notFound } from "next/navigation";
import { MOCK_CASES, getCaseRow } from "@/lib/mock-data";
import { CaseDetailView } from "./case-detail-view";

/**
 * Server shell for case detail.
 *
 * Next 16 runs with Cache Components enabled, so reading `params` outside a
 * Suspense boundary would block prerendering. The case set is static mock data
 * today, so the honest answer is to enumerate it with generateStaticParams.
 *
 * When Ismail's API lands (F4), this becomes a dynamic route: drop
 * generateStaticParams and either wrap the view in <Suspense> or set
 * `export const instant = false`.
 */
export function generateStaticParams() {
  return MOCK_CASES.map((row) => ({ id: row.id }));
}

export default async function CaseDetailPage({
  params,
}: PageProps<"/cases/[id]">) {
  const { id } = await params;
  if (!getCaseRow(id)) notFound();
  return <CaseDetailView id={id} />;
}
