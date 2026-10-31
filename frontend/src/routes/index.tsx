import { ApiError, auth, type LoginCredentials } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { BookOpen, GraduationCap, Paperclip, Star } from "lucide-react";
import { useState } from "react";
import { Btn, Field, inputCls } from "@/components/lk/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sign in · LAKSHYA Academic Assistant" },
      { name: "description", content: "Sign in to LAKSHYA as a student or faculty member." },
      { property: "og:title", content: "Sign in · LAKSHYA" },
      { property: "og:description", content: "Your academic journey, thoughtfully organised." },
    ],
  }),
  component: Login,
});

function Login() {
  const { login: completeLogin } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState<"student" | "faculty">("student");
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<{ id?: string; pw?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError(null);
    const n: typeof err = {};
    if (tab === "student" && !/^[A-Za-z0-9]{3,20}$/.test(id))
      n.id = "Enter a valid USN";
    if (tab === "faculty" && id.length < 3) n.id = "Enter your email or username";
    if (tab === "student" && !/^\d{4,6}$/.test(pw)) n.pw = "PIN must be 4–6 digits";
    if (tab === "faculty" && pw.length < 6) n.pw = "Password must be at least 6 characters";
    setErr(n);
    if (Object.keys(n).length) return;

    const credentials: LoginCredentials =
      tab === "student" ? { usn: id, pin: pw } : { email: id, password: pw };

    setLoading(true);
    try {
      const result = await auth.login(credentials);
      // Persist token + resolve the full user profile, then navigate.
      await completeLogin(result);
      await nav({ to: result.role === "student" ? "/student/home" : "/faculty/dashboard" });
    } catch (e) {
      if (e instanceof ApiError) {
        setServerError(e.message);
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen grid-cols-1 bg-taupe lg:grid-cols-2">
      <div className="stripes-wine relative overflow-hidden p-10">
        <div className="paper-wine relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-full border border-beige/50">
              <Star className="size-5 fill-beige text-beige" />
            </span>
            <span className="font-serif text-3xl font-bold tracking-[0.2em] text-ivory">
              LAKSHYA
            </span>
          </div>
          <div>
            <div className="eyebrow !text-beige/70">Vol. 05 — The Academic Assistant</div>
            <h1 className="display mt-4 text-6xl !text-ivory xl:text-7xl">
              Your academic journey, <em className="font-medium text-beige">thoughtfully</em>{" "}
              organised.
            </h1>
          </div>
          <div className="flex items-end gap-4">
            <div className="stamp rotate-[-6deg] bg-beige p-3 text-wine">
              <div className="grid size-20 place-items-center border border-wine/40">
                <GraduationCap className="size-9" strokeWidth={1.3} />
              </div>
            </div>
            <div className="relative rotate-[3deg] rounded-xl bg-ivory p-4 text-espresso shadow-[var(--shadow-lift)]">
              <Paperclip className="absolute -top-3 left-4 size-6 text-oxblood" />
              <div className="font-mono text-[10px] text-muted-foreground">NOTE · 19 OCT</div>
              <div className="font-serif text-lg text-wine">Quiz 3 opens Friday</div>
            </div>
            <div className="stamp rotate-[8deg] bg-dusty p-3 text-oxblood">
              <div className="grid size-16 place-items-center border border-oxblood/40">
                <BookOpen className="size-7" strokeWidth={1.3} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center bg-beige p-10">
        <form onSubmit={submit} className="paper w-full max-w-md p-10">
          <div className="eyebrow">Welcome back</div>
          <h2 className="display mt-2 text-4xl">Sign in to continue</h2>
          <div className="mt-6 grid grid-cols-2 rounded-full bg-beige p-1">
            {(["student", "faculty"] as const).map((t) => (
              <button
                type="button"
                key={t}
                onClick={() => {
                  setTab(t);
                  setErr({});
                  setServerError(null);
                }}
                className={cn(
                  "rounded-full py-2 text-sm capitalize transition",
                  tab === t ? "bg-wine text-ivory" : "text-wine",
                )}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="mt-6 space-y-4">
            <Field label={tab === "student" ? "USN" : "Email or username"} error={err.id}>
              <input
                value={id}
                onChange={(e) => setId(e.target.value)}
                placeholder={tab === "student" ? "1RV22CS018" : "meera.rao@college.edu"}
                className={cn(
                  inputCls,
                  tab === "student" && "font-mono uppercase",
                  err.id && "border-wine bg-wine/5",
                )}
              />
            </Field>
            <Field label={tab === "student" ? "PIN" : "Password"} error={err.pw}>
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                placeholder="••••••"
                className={cn(inputCls, err.pw && "border-wine bg-wine/5")}
              />
            </Field>
          </div>
          {serverError && (
            <div className="mt-2 rounded-full bg-oxblood/10 px-4 py-2 text-sm text-oxblood">
              {serverError}
            </div>
          )}
          <Btn size="lg" className="mt-8 w-full" disabled={loading}>
            {loading ? "Signing in…" : "Login"}
          </Btn>
          <p className="mt-6 text-center font-mono text-[10px] text-muted-foreground">
            © 2026 LAKSHYA · Need help? Contact your department office
          </p>
        </form>
      </div>
    </div>
  );
}
