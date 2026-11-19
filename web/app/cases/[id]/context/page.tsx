import { ContextView } from "./context-view";

export const instant = false;

export default async function ContextPage({
  params,
}: PageProps<"/cases/[id]/context">) {
  const { id } = await params;
  return <ContextView id={id} />;
}
