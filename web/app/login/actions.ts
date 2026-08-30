"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { NOME_COOKIE, criarCookieSessao, verificarCredenciais } from "../../lib/auth";

export async function entrar(formData: FormData) {
  const usuario = String(formData.get("usuario") ?? "").trim();
  const senha = String(formData.get("senha") ?? "");
  const proximo = String(formData.get("next") ?? "/") || "/";

  if (!verificarCredenciais(usuario, senha)) {
    redirect(`/login?erro=1&next=${encodeURIComponent(proximo)}`);
  }

  cookies().set(NOME_COOKIE, await criarCookieSessao(usuario), {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 30 * 24 * 60 * 60,
  });
  redirect(proximo);
}

export async function sair() {
  cookies().set(NOME_COOKIE, "", { path: "/", maxAge: 0 });
  redirect("/login");
}
