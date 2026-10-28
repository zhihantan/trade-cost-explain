import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "./App";
import { ApprovalQueue } from "./pages/ApprovalQueue";
import { AuditTrail } from "./pages/AuditTrail";
import { CommentaryList } from "./pages/CommentaryList";
import { CommentaryReview } from "./pages/CommentaryReview";
import { FluxOverview } from "./pages/FluxOverview";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: (n, e) => n < 2 && (e as { status?: number }).status !== 401 && (e as { status?: number }).status !== 403, refetchOnWindowFocus: false } },
});

// Data router (needed for the unsaved-changes blocker on the edit screen).
const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <FluxOverview /> },
      { path: "commentary", element: <CommentaryList /> },
      { path: "commentary/:id", element: <CommentaryReview /> },
      { path: "approvals", element: <ApprovalQueue /> },
      { path: "audit", element: <AuditTrail /> },
    ],
  },
], { future: { v7_relativeSplatPath: true } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </QueryClientProvider>
  </StrictMode>,
);
