import { createFileRoute } from "@tanstack/react-router";
import { isUUID4 } from "../api/client";
import { RunDetailPage } from "../features/runs/RunDetailPage";

export const Route = createFileRoute("/runs/$runId")({
  params: {
    parse: ({ runId }) => (isUUID4(runId) ? { runId } : false),
  },
  component: RunDetailPage,
});
