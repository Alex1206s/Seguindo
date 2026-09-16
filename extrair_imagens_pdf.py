#!/usr/bin/env python3
"""Extrai as imagens embutidas em um PDF (ex.: capturas de tela da lista de
"seguindo" exportadas como PDF) e gera uma listagem estruturada (JSON/CSV)
com os metadados de cada imagem.

Depende do utilitário `pdfimages`, do pacote poppler-utils:
    Debian/Ubuntu: apt install poppler-utils
    macOS (Homebrew): brew install poppler
"""

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

# A saída de `pdfimages -list` tem 16 colunas: o cabeçalho "object ID" é, na
# verdade, duas colunas separadas (número do objeto e número de geração).
CAMPOS = [
    "page", "num", "type", "width", "height", "color",
    "comp", "bpc", "enc", "interp", "object", "gen",
    "x_ppi", "y_ppi", "size", "ratio",
]


def verificar_pdfimages() -> None:
    if shutil.which("pdfimages") is None:
        sys.exit(
            "Erro: utilitário 'pdfimages' não encontrado no PATH.\n"
            "Instale o poppler-utils (ex.: apt install poppler-utils)."
        )


def parse_pdfimages_list(pdf_path: Path) -> list[dict]:
    """Executa `pdfimages -list` no PDF e retorna uma lista de dicts,
    um por imagem, com os metadados já convertidos para tipos nativos."""
    resultado = subprocess.run(
        ["pdfimages", "-list", str(pdf_path)],
        capture_output=True, text=True, check=True,
    )
    linhas = resultado.stdout.splitlines()
    # As duas primeiras linhas são o cabeçalho e o separador "----"
    linhas_dados = [ln for ln in linhas[2:] if ln.strip()]

    imagens = []
    for linha in linhas_dados:
        campos = linha.split()
        if len(campos) < len(CAMPOS):
            continue
        registro = dict(zip(CAMPOS, campos))
        for chave in ("page", "num", "width", "height", "object", "gen"):
            registro[chave] = int(registro[chave])
        imagens.append(registro)
    return imagens


def extrair_imagens(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Extrai as imagens embutidas no PDF como arquivos PNG em out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    prefixo = out_dir / pdf_path.stem
    subprocess.run(["pdfimages", "-png", str(pdf_path), str(prefixo)], check=True)
    return sorted(out_dir.glob(f"{pdf_path.stem}-*.png"))


def salvar_listagem(imagens: list[dict], destino: Path, formato: str) -> None:
    if formato == "json":
        destino.write_text(json.dumps(imagens, indent=2, ensure_ascii=False))
    else:
        with destino.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CAMPOS)
            writer.writeheader()
            writer.writerows(imagens)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai imagens de um PDF e lista seus metadados de forma estruturada."
    )
    parser.add_argument("pdf", type=Path, help="Caminho do arquivo PDF de origem")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("imagens_extraidas"),
        help="Diretório onde as imagens e a listagem serão salvas (padrão: imagens_extraidas)",
    )
    parser.add_argument(
        "--formato", choices=["json", "csv"], default="json",
        help="Formato da listagem de metadados (padrão: json)",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        sys.exit(f"Erro: arquivo não encontrado: {args.pdf}")

    verificar_pdfimages()

    imagens_meta = parse_pdfimages_list(args.pdf)
    arquivos_extraidos = extrair_imagens(args.pdf, args.output_dir)

    print(f"{len(imagens_meta)} imagens encontradas em '{args.pdf.name}'.")
    print(f"{len(arquivos_extraidos)} arquivos extraídos em '{args.output_dir}'.")

    listagem_path = args.output_dir / f"listagem.{args.formato}"
    salvar_listagem(imagens_meta, listagem_path, args.formato)
    print(f"Listagem salva em '{listagem_path}'.")


if __name__ == "__main__":
    main()
