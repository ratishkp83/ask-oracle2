import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "./app/AppShell";
import { PlaceholderPage } from "./app/PlaceholderPage";
import { AskPage } from "./features/ask/AskPage";
import { ConnectionsPage } from "./features/connections/ConnectionsPage";
import { DataDictionaryPage } from "./features/dictionary/DataDictionaryPage";
import { ReportsPage } from "./features/reports/ReportsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/ask" replace /> },
      { path: "ask", element: <AskPage /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "dictionary", element: <DataDictionaryPage /> },
      { path: "connections", element: <ConnectionsPage /> },
      {
        path: "settings",
        element: <PlaceholderPage title="Settings" subtitle="Model and email configuration." />,
      },
      { path: "*", element: <PlaceholderPage title="Not found" subtitle="That screen doesn't exist yet." /> },
    ],
  },
]);
