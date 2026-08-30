import { entrar } from "./actions";

export default function Login({
  searchParams,
}: {
  searchParams: { [key: string]: string | undefined };
}) {
  const proximo = searchParams.next ?? "/";
  const erro = searchParams.erro === "1";

  return (
    <main className="pagina-login">
      <form className="cartao-login" action={entrar}>
        <h1>Análise de Mercado</h1>
        <p className="marca">À Frente Soluções</p>
        <p className="subtitulo">Acesso restrito à equipe.</p>

        <input type="hidden" name="next" value={proximo} />

        <div className="campo">
          <label htmlFor="usuario">Usuário</label>
          <input id="usuario" name="usuario" type="text" autoFocus required />
        </div>
        <div className="campo">
          <label htmlFor="senha">Senha</label>
          <input id="senha" name="senha" type="password" required />
        </div>

        {erro && <p className="erro-login">Usuário ou senha incorretos.</p>}

        <button type="submit">Entrar</button>
      </form>
    </main>
  );
}
