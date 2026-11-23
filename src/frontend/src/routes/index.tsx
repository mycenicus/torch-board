import { createFileRoute } from "@tanstack/react-router";
import { ExperimentsPage } from "../features/experiments/ExperimentsPage";

export const Route = createFileRoute("/")({
  component: ExperimentsPage,
});
