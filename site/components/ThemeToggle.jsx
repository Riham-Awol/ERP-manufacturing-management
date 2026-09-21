"use client";

import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState(null);

  useEffect(() => {
    try {
      setTheme(localStorage.getItem("aifa-theme"));
    } catch {
      /* private mode: fall back to the OS setting */
    }
  }, []);

  function toggle() {
    const current =
      theme ??
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    setTheme(next);
    try {
      localStorage.setItem("aifa-theme", next);
    } catch {
      /* not persisting is fine; the page still switches */
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Switch between light and dark"
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border-strong)",
        color: "var(--text-secondary)",
        borderRadius: 8,
        padding: "5px 10px",
        fontSize: ".82rem",
        cursor: "pointer",
      }}
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
