import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "./app/AppShell";
import { PlaceholderPage } from "./app/PlaceholderPage";
import { AskPage } from "./features/ask/AskPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/ask" replace /> },
      { path: "ask", element: <AskPage /> },
      {
        path: "reports",
        element: <PlaceholderPage title="Reports" subtitle="Saved reports — run, refine, and re-share." />,
      },
      {
        path: "dictionary",
        element: (
          <PlaceholderPage
            title="Data dictionary"
            subtitle="Browse schemas and curated EBS module packs (GL · AP · AR · PO · OM)."
          />
        ),
      },
      {
        path: "connections",
        element: <PlaceholderPage title="Connections" subtitle="Pick and test the database connection." />,
      },
      {
        path: "settings",
        element: <PlaceholderPage title="Settings" subtitle="Model and email configuration." />,
      },
      { path: "*", element: <PlaceholderPage title="Not found" subtitle="That screen doesn't exist yet." /> },
    ],
  },
]);
