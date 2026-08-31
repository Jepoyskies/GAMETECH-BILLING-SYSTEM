import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import gametechLogo from "../assets/gametech-logo-white.png";
import "../styles/Auth.css";
import "../styles/Forms.css";

export default function Login() {
  const { needsSetup, login, setup } = useAuth();
  const { addToast } = useToast();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (error) addToast(error, "error");
  }, [error]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (needsSetup) {
        await setup(name.trim(), email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-shell">
        <div className="auth-welcome">
          <div className="auth-welcome-content">
            <img
              src={gametechLogo}
              alt="Gametech"
              style={{
                maxWidth: "80%",
                maxHeight: "60px",
                height: "auto",
                display: "block",
                marginBottom: "1rem",
              }}
            />
            <h1 className="auth-welcome-title">
              {needsSetup ? "Welcome" : "Welcome back"}
            </h1>
            <p className="auth-welcome-text">
              {needsSetup
                ? "Set up the first account for your team. This account becomes the SUPERADMIN with full access to manage dispatch monitoring."
                : "Sign in to keep track of dispatches, monitor ongoing records, and manage CSR operations."}
            </p>
          </div>
        </div>

        <form className="auth-card" onSubmit={handleSubmit}>
          <h2 className="auth-title">
            {needsSetup ? "Create SUPERADMIN account" : "Sign in"}
          </h2>
          <p className="auth-subtitle">
            {needsSetup
              ? "Fill in your details to get started."
              : "Enter your credentials to continue."}
          </p>

          {needsSetup && (
            <div className="auth-field">
              <label>Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                required
                disabled={submitting}
              />
            </div>
          )}

          <div className="auth-field">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
              disabled={submitting}
            />
          </div>

          <div className="auth-field">
            <label>Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={needsSetup ? "new-password" : "current-password"}
                required
                disabled={submitting}
                minLength={needsSetup ? 8 : undefined}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button className="auth-submit" type="submit" disabled={submitting}>
            {submitting
              ? "Please wait…"
              : needsSetup
                ? "Create SUPERADMIN account"
                : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}