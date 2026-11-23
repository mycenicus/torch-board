import { createFileRoute } from "@tanstack/react-router";
import { ExperimentDetailPage } from "../features/experiments/ExperimentDetailPage";

export const Route = createFileRoute("/experiments/$experimentId")({
  params: {
    parse: ({ experimentId }) => {
      if (!/^[1-9]\d*$/.test(experimentId)) {
        return false;
      }

      const parsedId = Number(experimentId);
      return Number.isSafeInteger(parsedId) ? { experimentId: parsedId } : false;
    },
    stringify: ({ experimentId }) => ({ experimentId: String(experimentId) }),
  },
  component: ExperimentDetailPage,
});
