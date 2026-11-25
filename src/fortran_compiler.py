"""Interface de linha de comandos (CLI) do compilador Fortran 77.

Nesta Fase 1 suporta a opção `--tokens` para executar a análise léxica e
apresentar os tokens, avisos e erros encontrados. As opções das fases futuras
(`-o`, `--ir`, `-O`) já estão estruturadas no `argparse`.
"""

import argparse
import sys
from pathlib import Path

# Permitir execução direta (`python src/fortran_compiler.py ...`) ou como módulo.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.lexer import tokenize_with_diagnostics


def build_arg_parser():
    """Cria o parser de argumentos da linha de comandos."""
    parser = argparse.ArgumentParser(
        prog="fortran_compiler.py",
        description="Compilador de Fortran 77 (ANSI X3.9-1978) para EWVM.",
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Caminho para o ficheiro fonte Fortran (.f).",
    )
    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Executa apenas a análise léxica e imprime os tokens produzidos.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="(Fases futuras) Ficheiro de saída de código EWVM (.vm).",
    )
    parser.add_argument(
        "--ir",
        action="store_true",
        help="(Fases futuras) Imprime a representação intermédia gerada.",
    )
    parser.add_argument(
        "-O",
        "--optimize",
        action="store_true",
        help="(Fases futuras) Ativa otimizações de código.",
    )
    return parser


def run_lex_only(source_path):
    """Corre a análise léxica sobre `source_path` e imprime o resultado."""
    if not source_path.is_file():
        print(f"Erro: ficheiro não encontrado: '{source_path}'", file=sys.stderr)
        return 1

    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Erro ao ler '{source_path}': {exc}", file=sys.stderr)
        return 1

    tokens_list, errors, warnings = tokenize_with_diagnostics(source)

    print(f"{'TIPO':<18} {'VALOR':<32} {'LINHA':>5} {'COL':>5}")
    print("-" * 64)
    for tok in tokens_list:
        col = getattr(tok, "col", 0)
        print(f"{tok.type:<18} {repr(tok.value):<32} {tok.lineno:>5} {col:>5}")

    if warnings:
        print("\nAvisos:", file=sys.stderr)
        for warn in warnings:
            print(f"  {warn}", file=sys.stderr)

    if errors:
        print("\nErros:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    return 0


def main(argv=None):
    """Ponto de entrada principal da CLI."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.tokens:
        return run_lex_only(args.source)

    print(
        "Aviso: apenas a Fase 1 (Análise Léxica) está implementada. "
        "Utilize a opção '--tokens' para inspecionar os tokens.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())