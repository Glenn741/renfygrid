import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, login } from "../api";
import { useAuth } from "../auth";

export function LoginPage() {
  const { setAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [tenantId, setTenantId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await login({ tenant_id: tenantId, email, password });
      setAuthenticated(response.access_token);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? "Usuario, contraseña u organización incorrectos." : "No se pudo conectar con RenfyGrid.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-2xl border border-white/10 bg-white p-8 shadow-2xl">
        <div className="flex items-center gap-2 mb-1">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-bold text-sm">
            R
          </span>
          <h1 className="text-xl font-bold text-slate-900">RenfyGrid</h1>
        </div>
        <p className="text-sm text-slate-500 mb-6">Portal operativo</p>

        <label htmlFor="login-tenant" className="block text-sm font-medium text-slate-700 mb-1">Organización</label>
        <input
          id="login-tenant"
          name="tenant_id"
          autoComplete="organization"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 mb-4 text-sm"
          value={tenantId}
          onChange={(e) => setTenantId(e.target.value)}
          placeholder="nombre o id (p. ej. jaas001)"
          required
        />

        <label htmlFor="login-user" className="block text-sm font-medium text-slate-700 mb-1">Usuario</label>
        <input
          id="login-user"
          type="text"
          name="username"
          autoComplete="username"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 mb-4 text-sm"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <label htmlFor="login-password" className="block text-sm font-medium text-slate-700 mb-1">Contraseña</label>
        <input
          id="login-password"
          type="password"
          name="password"
          autoComplete="current-password"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 mb-6 text-sm"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-indigo-600 text-white text-sm font-semibold py-2 hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? "Ingresando..." : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
