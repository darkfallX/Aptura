import { notFound } from "next/navigation";
import RequestDetail from "@/components/x/RequestDetail";
import { requestById, requests } from "@/lib/requests";

export function generateStaticParams() {
  return requests.map((r) => ({ id: r.id }));
}

export default async function RequestPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = requestById(id);
  if (!r) notFound();
  return <RequestDetail r={r} />;
}
