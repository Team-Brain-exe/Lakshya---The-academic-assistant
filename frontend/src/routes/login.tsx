import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

/**
 * The login page lives at `/` (see routes/index.tsx).
 * This route exists so the API client's 401 redirect target (`/login`)
 * lands on a valid route — it simply forwards to `/`.
 */
function LoginRedirect() {
  const nav = useNavigate();
  useEffect(() => {
    void nav({ to: "/" });
  }, [nav]);
  return null;
}

export const Route = createFileRoute("/login")({
  component: LoginRedirect,
});
