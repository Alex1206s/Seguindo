#!/usr/bin/env python3
"""
Extrai a lista completa de "seguindo" de um perfil do Instagram a partir da URL,
autenticando com uma conta que você administra.

Uso:
    python3 extrair_seguindo.py --url https://www.instagram.com/exemplo/

A conta usada para logar (variáveis de ambiente INSTA_LOGIN / INSTA_SENHA, ou
prompt interativo) precisa ter permissão para ver a lista de "seguindo" do
perfil informado na URL: perfil público, perfil próprio, ou perfil privado
que a conta logada já segue (pedido aceito).

O resultado é salvo em dados/<usuario>/<usuario>_<timestamp>.json e comparado
automaticamente com a extração anterior, gerando um relatório de entradas e
saídas (quem passou a ser seguido / deixou de ser seguido entre uma execução
e outra).
"""

import argparse
import getpass
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    LoginRequiredException,
    TwoFactorAuthRequiredException,
    BadCredentialsException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("extrair_seguindo")

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"
SESSOES_DIR = BASE_DIR / ".sessoes"

MAX_TENTATIVAS = 5
ESPERA_BASE_SEGUNDOS = 30  # backoff exponencial em caso de rate limit


def extrair_username_do_link(url: str) -> str:
    """Extrai o @username a partir de uma URL de perfil do Instagram."""
    url = url.strip()
    if not url.startswith("http"):
        # já veio como @usuario ou usuario puro
        return url.lstrip("@")

    caminho = urlparse(url).path.strip("/")
    partes = [p for p in caminho.split("/") if p]
    if not partes:
        raise ValueError(f"Não foi possível extrair um usuário da URL: {url}")

    usuario = partes[0]
    if not re.match(r"^[A-Za-z0-9._]{1,30}$", usuario):
        raise ValueError(f"Usuário inválido extraído da URL: {usuario!r}")
    return usuario


def criar_loader() -> instaloader.Instaloader:
    return instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=3,
    )


def login(loader: instaloader.Instaloader, login_conta: str, senha: str | None) -> None:
    """Autentica reaproveitando sessão salva em disco sempre que possível,
    para reduzir o número de logins (evita bloqueios/checkpoints)."""
    SESSOES_DIR.mkdir(exist_ok=True)
    arquivo_sessao = SESSOES_DIR / f"session-{login_conta}"

    if arquivo_sessao.exists():
        try:
            loader.load_session_from_file(login_conta, filename=str(arquivo_sessao))
            log.info("Sessão existente carregada para @%s", login_conta)
            return
        except Exception:
            log.warning("Sessão salva inválida/expirada, autenticando novamente.")

    if not senha:
        senha = os.environ.get("INSTA_SENHA") or getpass.getpass(
            f"Senha da conta @{login_conta}: "
        )

    try:
        loader.login(login_conta, senha)
    except TwoFactorAuthRequiredException:
        codigo = input("Código de autenticação em duas etapas: ").strip()
        loader.two_factor_login(codigo)
    except BadCredentialsException:
        log.error("Usuário ou senha incorretos para @%s.", login_conta)
        sys.exit(1)

    loader.save_session_to_file(filename=str(arquivo_sessao))
    log.info("Login efetuado e sessão salva para @%s", login_conta)


def extrair_seguindo(loader: instaloader.Instaloader, username_alvo: str) -> list[dict]:
    """Extrai 100% da lista de seguindo do perfil, com retry/backoff em caso
    de erro de conexão ou rate limit do Instagram."""
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            perfil = instaloader.Profile.from_username(loader.context, username_alvo)
            total_esperado = perfil.followees
            log.info(
                "Perfil @%s: %d contas seguidas (extraindo...)",
                username_alvo,
                total_esperado,
            )

            seguindo = []
            for i, seguido in enumerate(perfil.get_followees(), start=1):
                seguindo.append(
                    {
                        "id": seguido.userid,
                        "username": seguido.username,
                        "nome_completo": seguido.full_name,
                        "privado": seguido.is_private,
                        "verificado": seguido.is_verified,
                    }
                )
                if i % 200 == 0:
                    log.info("  ... %d/%d extraídos", i, total_esperado)

            if len(seguindo) < total_esperado:
                log.warning(
                    "Extraídos %d de %d esperados — Instagram pode ter cortado a "
                    "paginação; tentando novamente.",
                    len(seguindo),
                    total_esperado,
                )
                raise ConnectionException("Extração incompleta")

            log.info("Extração completa: %d/%d contas.", len(seguindo), total_esperado)
            return seguindo

        except ProfileNotExistsException:
            log.error("Perfil @%s não existe (ou o link está errado).", username_alvo)
            sys.exit(1)
        except PrivateProfileNotFollowedException:
            log.error(
                "Perfil @%s é privado e a conta logada não o segue (ou o pedido "
                "de seguir ainda está pendente). Aceite o pedido primeiro, ou "
                "logue com uma conta que já o siga.",
                username_alvo,
            )
            sys.exit(1)
        except LoginRequiredException:
            raise
        except ConnectionException as e:
            espera = ESPERA_BASE_SEGUNDOS * (2 ** (tentativa - 1))
            log.warning(
                "Tentativa %d/%d falhou (%s). Aguardando %ds antes de tentar de novo...",
                tentativa,
                MAX_TENTATIVAS,
                e,
                espera,
            )
            time.sleep(espera)

    raise RuntimeError(
        f"Não foi possível extrair a lista de seguindo de @{username_alvo} "
        f"após {MAX_TENTATIVAS} tentativas."
    )


def salvar_resultado(username_alvo: str, seguindo: list[dict]) -> Path:
    pasta = DADOS_DIR / username_alvo
    pasta.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arquivo = pasta / f"{username_alvo}_{timestamp}.json"

    with arquivo.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "perfil": username_alvo,
                "extraido_em": timestamp,
                "total": len(seguindo),
                "seguindo": seguindo,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    log.info("Resultado salvo em %s", arquivo)
    return arquivo


def comparar_com_anterior(username_alvo: str, arquivo_atual: Path) -> None:
    pasta = DADOS_DIR / username_alvo
    anteriores = sorted(
        p for p in pasta.glob(f"{username_alvo}_*.json") if p != arquivo_atual
    )
    if not anteriores:
        log.info("Nenhuma extração anterior encontrada — nada a comparar ainda.")
        return

    arquivo_anterior = anteriores[-1]
    with arquivo_anterior.open(encoding="utf-8") as f:
        dados_antes = json.load(f)
    with arquivo_atual.open(encoding="utf-8") as f:
        dados_agora = json.load(f)

    usuarios_antes = {c["username"] for c in dados_antes["seguindo"]}
    usuarios_agora = {c["username"] for c in dados_agora["seguindo"]}

    novos = sorted(usuarios_agora - usuarios_antes)
    removidos = sorted(usuarios_antes - usuarios_agora)

    print("\n=== Comparação com a extração anterior ===")
    print(f"Extração anterior: {dados_antes['extraido_em']} ({len(usuarios_antes)} contas)")
    print(f"Extração atual:    {dados_agora['extraido_em']} ({len(usuarios_agora)} contas)")
    print(f"\nPassou a seguir ({len(novos)}):")
    for u in novos:
        print(f"  + {u}")
    print(f"\nDeixou de seguir ({len(removidos)}):")
    for u in removidos:
        print(f"  - {u}")


def main():
    parser = argparse.ArgumentParser(
        description="Extrai a lista completa de 'seguindo' de um perfil do Instagram."
    )
    parser.add_argument("--url", required=True, help="URL (ou @usuario) do perfil alvo")
    parser.add_argument(
        "--login",
        default=os.environ.get("INSTA_LOGIN"),
        help="Usuário da conta que fará login (ou defina INSTA_LOGIN)",
    )
    parser.add_argument(
        "--senha",
        default=None,
        help="Senha da conta (evite passar em texto puro; prefira INSTA_SENHA ou prompt)",
    )
    args = parser.parse_args()

    if not args.login:
        args.login = input("Usuário da conta para login: ").strip()

    username_alvo = extrair_username_do_link(args.url)

    loader = criar_loader()
    login(loader, args.login, args.senha)

    seguindo = extrair_seguindo(loader, username_alvo)
    arquivo = salvar_resultado(username_alvo, seguindo)
    comparar_com_anterior(username_alvo, arquivo)


if __name__ == "__main__":
    main()
