import { createFileRoute } from "@tanstack/react-router";
import { isUUID4, parseUUID4 } from "../api/client";
import { RunDetailPage } from "../features/runs/RunDetailPage";

export const Route = createFileRoute("/runs/$runId")({
  params: {
    parse: ({ runId }) => (isUUID4(runId) ? { runId: parseUUID4(runId.toLowerCase()) } : false),
  },
  component: RunDetailPage,
});
