"""Bateria de testes automáticos para o analisador léxico (Fase 1)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from src.lexer import build_lexer, reserved, tokenize, tokenize_with_diagnostics

TESTS_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = TESTS_DIR / "examples"
LEXER_CASES_DIR = TESTS_DIR / "lexer"


def _pairs(source: str) -> list[tuple[str, object]]:
    """Devolve lista de `(tipo, valor)` sem `NEWLINE` para asserções concisas."""
    toks, errors = tokenize(source)
    assert errors == [], f"Erros inesperados: {errors}"
    return [(t.type, t.value) for t in toks if t.type != "NEWLINE"]


# ======================================================================
# 1. Testes unitários por categoria
# ======================================================================

@pytest.mark.parametrize("kw,expected_type", list(reserved.items()))
def test_all_single_keywords(kw: str, expected_type: str) -> None:
    """Todas as palavras-chave simples são reconhecidas (incluindo minúsculas)."""
    for variant in (kw, kw.lower(), kw.capitalize()):
        toks, errors = tokenize(f"  {variant}\n")
        assert errors == []
        assert toks[0].type == expected_type
        assert toks[0].value == kw


@pytest.mark.parametrize(
    "text,expected_type,expected_value",
    [
        ("GO TO", "GOTO", "GOTO"),
        ("go   to", "GOTO", "GOTO"),
        ("END IF", "ENDIF", "ENDIF"),
        ("end if", "ENDIF", "ENDIF"),
        ("ELSE IF", "ELSEIF", "ELSEIF"),
        ("else\tif", "ELSEIF", "ELSEIF"),
        ("END DO", "ENDDO", "ENDDO"),
        ("DOUBLE PRECISION", "DOUBLE_PRECISION", "DOUBLE PRECISION"),
        ("BLOCK DATA", "BLOCK_DATA", "BLOCK DATA"),
    ],
)
def test_two_word_keywords(text: str, expected_type: str, expected_value: str) -> None:
    """Palavras-chave de duas palavras produzem um único token."""
    toks, errors = tokenize(f"  {text}\n")
    assert errors == []
    assert [(t.type, t.value) for t in toks if t.type != "NEWLINE"] == [
        (expected_type, expected_value)
    ]


def test_intrinsics_are_identifiers() -> None:
    """Funções intrínsecas saem como ID e são tratadas na análise semântica."""
    assert _pairs("  X = MOD(ABS(Y), SQRT(Z)) + MAX(A, MIN(B, C))") == [
        ("ID", "X"),
        ("ASSIGN", "="),
        ("ID", "MOD"),
        ("LPAREN", "("),
        ("ID", "ABS"),
        ("LPAREN", "("),
        ("ID", "Y"),
        ("RPAREN", ")"),
        ("COMMA", ","),
        ("ID", "SQRT"),
        ("LPAREN", "("),
        ("ID", "Z"),
        ("RPAREN", ")"),
        ("RPAREN", ")"),
        ("PLUS", "+"),
        ("ID", "MAX"),
        ("LPAREN", "("),
        ("ID", "A"),
        ("COMMA", ","),
        ("ID", "MIN"),
        ("LPAREN", "("),
        ("ID", "B"),
        ("COMMA", ","),
        ("ID", "C"),
        ("RPAREN", ")"),
        ("RPAREN", ")"),
    ]


def test_identifiers_and_case_insensitivity() -> None:
    """Identificadores são normalizados para maiúsculas e aceitam '_'."""
    assert _pairs("  var1 = Outro_Nome + x") == [
        ("ID", "VAR1"),
        ("ASSIGN", "="),
        ("ID", "OUTRO_NOME"),
        ("PLUS", "+"),
        ("ID", "X"),
    ]


def test_integers_and_reals() -> None:
    """Inteiros e todas as variantes de literais reais (E e D)."""
    src = "  X = 42 + 3.14 + .5 + 2. + 1.0E-5 + 1E3 + 1.0D0 + 1.0D-3"
    pairs = _pairs(src)
    assert pairs == [
        ("ID", "X"),
        ("ASSIGN", "="),
        ("INTEGER_CONST", 42),
        ("PLUS", "+"),
        ("REAL_CONST", pytest.approx(3.14)),
        ("PLUS", "+"),
        ("REAL_CONST", pytest.approx(0.5)),
        ("PLUS", "+"),
        ("REAL_CONST", pytest.approx(2.0)),
        ("PLUS", "+"),
        ("REAL_CONST", pytest.approx(1.0e-5)),
        ("PLUS", "+"),
        ("REAL_CONST", pytest.approx(1000.0)),
        ("PLUS", "+"),
        ("REAL_CONST", pytest.approx(1.0)),
        ("PLUS", "+"),
        ("REAL_CONST", pytest.approx(1.0e-3)),
    ]


def test_logical_literals() -> None:
    """Literais lógicos produzem valor booleano Python."""
    assert _pairs("  A = .TRUE.\n  B = .false.") == [
        ("ID", "A"),
        ("ASSIGN", "="),
        ("LOGICAL_CONST", True),
        ("ID", "B"),
        ("ASSIGN", "="),
        ("LOGICAL_CONST", False),
    ]


def test_strings_escape_and_bang() -> None:
    """Strings preservam maiúsculas/minúsculas, tratam '' e ignoram '!' interno."""
    assert _pairs("  S = 'Ola ''Mundo'' ! tudo bem'") == [
        ("ID", "S"),
        ("ASSIGN", "="),
        ("STRING_CONST", "Ola 'Mundo' ! tudo bem"),
    ]


def test_all_operators_and_punctuation() -> None:
    """Todos os operadores aritméticos, relacionais, lógicos e pontuação."""
    src = (
        "  A + B - C * D / E ** F // G\n"
        "  .EQ. .NE. .LT. .LE. .GT. .GE.\n"
        "  .AND. .OR. .NOT. .EQV. .NEQV.\n"
        "  (A, B:C)\n"
    )
    types = [t for t, _ in _pairs(src)]
    assert types == [
        "ID", "PLUS", "ID", "MINUS", "ID", "STAR", "ID", "SLASH", "ID", "POWER", "ID", "CONCAT", "ID",
        "EQ", "NE", "LT", "LE", "GT", "GE",
        "AND", "OR", "NOT", "EQV", "NEQV",
        "LPAREN", "ID", "COMMA", "ID", "COLON", "ID", "RPAREN",
    ]


def test_format_spec_and_warning() -> None:
    """FORMAT captura o especificador cru como FORMAT_SPEC e emite aviso."""
    toks, errors, warnings = tokenize_with_diagnostics("  10 FORMAT (I5, 2X, F8.2)\n")
    assert errors == []
    assert any("FORMAT" in w.message for w in warnings)
    assert [(t.type, t.value) for t in toks] == [
        ("LABEL", 10),
        ("FORMAT", "FORMAT"),
        ("FORMAT_SPEC", "(I5, 2X, F8.2)"),
        ("NEWLINE", "\n"),
    ]


# ======================================================================
# 2. Comentários, labels, fins de linha e preservação de linha/coluna
# ======================================================================

def test_comments_blank_lines_and_crlf() -> None:
    """Comentários C/c/*/!, linhas em branco e \\r\\n são tratados corretamente."""
    src = (
        "C comentario maiusculo\r\n"
        "c comentario minusculo\r\n"
        "* comentario asterisco\r\n"
        "   ! comentario com espacos\r\n"
        "\r\n"
        "  X = 1 ! comentario inline\r\n"
        "  10 CONTINUE"
    )
    toks, errors = tokenize(src)
    assert errors == []
    assert [(t.type, t.value, t.lineno) for t in toks] == [
        ("ID", "X", 6),
        ("ASSIGN", "=", 6),
        ("INTEGER_CONST", 1, 6),
        ("NEWLINE", "\n", 6),
        ("LABEL", 10, 7),
        ("CONTINUE", "CONTINUE", 7),
        ("NEWLINE", "\n", 7),
    ]


def test_label_vs_integer_const() -> None:
    """Apenas o número no início da instrução é LABEL; os restantes são INTEGER_CONST."""
    src = "  DO 10 I = 1, 5\n  10 CONTINUE\n  GOTO 10\n"
    toks, errors = tokenize(src)
    assert errors == []
    assert [(t.type, t.value) for t in toks if t.type != "NEWLINE"] == [
        ("DO", "DO"),
        ("INTEGER_CONST", 10),
        ("ID", "I"),
        ("ASSIGN", "="),
        ("INTEGER_CONST", 1),
        ("COMMA", ","),
        ("INTEGER_CONST", 5),
        ("LABEL", 10),
        ("CONTINUE", "CONTINUE"),
        ("GOTO", "GOTO"),
        ("INTEGER_CONST", 10),
    ]


# ======================================================================
# 3. Ambiguidades clássicas (R3)
# ======================================================================

def test_ambiguity_dot_operators_next_to_numbers() -> None:
    """1.EQ.2, 5.AND.X, X.LT.5. e A.EQ.B são tokenizados corretamente."""
    assert _pairs("  F = 1.EQ.2") == [
        ("ID", "F"), ("ASSIGN", "="), ("INTEGER_CONST", 1), ("EQ", ".EQ."), ("INTEGER_CONST", 2),
    ]
    assert _pairs("  F = 5.AND.X") == [
        ("ID", "F"), ("ASSIGN", "="), ("INTEGER_CONST", 5), ("AND", ".AND."), ("ID", "X"),
    ]
    assert _pairs("  X.LT.5.") == [("ID", "X"), ("LT", ".LT."), ("REAL_CONST", 5.0)]
    assert _pairs("  A.EQ.B") == [("ID", "A"), ("EQ", ".EQ."), ("ID", "B")]


def test_ambiguity_power_vs_star_and_io_star() -> None:
    """** vs * e reutilização de STAR em CHARACTER*10 e PRINT *,."""
    assert _pairs("  X = A**2*3") == [
        ("ID", "X"), ("ASSIGN", "="), ("ID", "A"),
        ("POWER", "**"), ("INTEGER_CONST", 2), ("STAR", "*"), ("INTEGER_CONST", 3),
    ]
    assert _pairs("  CHARACTER*10 NOME") == [
        ("CHARACTER", "CHARACTER"), ("STAR", "*"), ("INTEGER_CONST", 10), ("ID", "NOME"),
    ]
    assert _pairs("  READ(*,*) X") == [
        ("READ", "READ"), ("LPAREN", "("), ("STAR", "*"), ("COMMA", ","),
        ("STAR", "*"), ("RPAREN", ")"), ("ID", "X"),
    ]


def test_ambiguity_end_variants() -> None:
    """END sozinho não é confundido com END IF / END DO; END pode ter label."""
    src = "  END IF\n  END DO\n  100 END\n"
    assert _pairs(src) == [
        ("ENDIF", "ENDIF"),
        ("ENDDO", "ENDDO"),
        ("LABEL", 100),
        ("END", "END"),
    ]


# ======================================================================
# 4. Erros léxicos intencionais e recuperação
# ======================================================================

def test_illegal_characters_and_recovery() -> None:
    """Caracteres ilegais são reportados com linha/coluna sem abortar."""
    src = "  A = @ + #\n  B = 1\n"
    toks, errors = tokenize(src)
    assert len(errors) == 2
    assert (errors[0].line, errors[0].column) == (1, 7)
    assert (errors[1].line, errors[1].column) == (1, 11)
    assert ("ID", "B") in [(t.type, t.value) for t in toks]


def test_unterminated_string_malformed_numbers_and_unknown_dot_op() -> None:
    """String sem fecho, 1.2.3, 1E+, .FOO., label > 5 dígitos e Hollerith."""
    src = (
        "  S = 'sem fecho\n"
        "  X = 1.2.3\n"
        "  Y = 1E+\n"
        "  Z = A .FOO. B\n"
        "  123456 CONTINUE\n"
        "  H = 5HHELLO\n"
    )
    _toks, errors = tokenize(src)
    assert len(errors) == 6
    assert [e.line for e in errors] == [1, 2, 3, 4, 5, 6]


def test_build_lexer_isolation_and_yacc_interface() -> None:
    """build_lexer() cria instâncias isoladas com interface input()/token()."""
    lex1 = build_lexer()
    lex2 = build_lexer()
    lex1.input("  @\n")
    lex2.input("  X = 1\n")
    assert len(lex1.errors) == 1
    assert len(lex2.errors) == 0

    stream = []
    while True:
        tok = lex2.token()
        if tok is None:
            break
        stream.append(tok.type)
    assert stream == ["ID", "ASSIGN", "INTEGER_CONST", "NEWLINE"]


# ======================================================================
# 5. Integração com os 7 exemplos do enunciado
# ======================================================================

def test_example_01_hello_exact() -> None:
    source = (EXAMPLES_DIR / "01_hello.f").read_text(encoding="utf-8")
    toks, errors = tokenize(source)
    assert errors == []
    assert [(t.type, t.value) for t in toks] == [
        ("PROGRAM", "PROGRAM"), ("ID", "HELLO"), ("NEWLINE", "\n"),
        ("PRINT", "PRINT"), ("STAR", "*"), ("COMMA", ","), ("STRING_CONST", "Ola, Mundo!"), ("NEWLINE", "\n"),
        ("END", "END"), ("NEWLINE", "\n"),
    ]


def test_example_02_fatorial_exact() -> None:
    source = (EXAMPLES_DIR / "02_fatorial.f").read_text(encoding="utf-8")
    toks, errors = tokenize(source)
    assert errors == []
    assert [(t.type, t.value) for t in toks] == [
        ("PROGRAM", "PROGRAM"), ("ID", "FATORIAL"), ("NEWLINE", "\n"),
        ("INTEGER", "INTEGER"), ("ID", "N"), ("COMMA", ","), ("ID", "I"), ("COMMA", ","), ("ID", "FAT"), ("NEWLINE", "\n"),
        ("PRINT", "PRINT"), ("STAR", "*"), ("COMMA", ","), ("STRING_CONST", "Introduza um numero inteiro positivo:"), ("NEWLINE", "\n"),
        ("READ", "READ"), ("STAR", "*"), ("COMMA", ","), ("ID", "N"), ("NEWLINE", "\n"),
        ("ID", "FAT"), ("ASSIGN", "="), ("INTEGER_CONST", 1), ("NEWLINE", "\n"),
        ("DO", "DO"), ("INTEGER_CONST", 10), ("ID", "I"), ("ASSIGN", "="), ("INTEGER_CONST", 1), ("COMMA", ","), ("ID", "N"), ("NEWLINE", "\n"),
        ("ID", "FAT"), ("ASSIGN", "="), ("ID", "FAT"), ("STAR", "*"), ("ID", "I"), ("NEWLINE", "\n"),
        ("LABEL", 10), ("CONTINUE", "CONTINUE"), ("NEWLINE", "\n"),
        ("PRINT", "PRINT"), ("STAR", "*"), ("COMMA", ","), ("STRING_CONST", "Fatorial de "), ("COMMA", ","),
        ("ID", "N"), ("COMMA", ","), ("STRING_CONST", ": "), ("COMMA", ","), ("ID", "FAT"), ("NEWLINE", "\n"),
        ("END", "END"), ("NEWLINE", "\n"),
    ]


def test_example_03_primo_exact() -> None:
    source = (EXAMPLES_DIR / "03_primo.f").read_text(encoding="utf-8")
    toks, errors = tokenize(source)
    assert errors == []
    assert [(t.type, t.value) for t in toks if t.type != "NEWLINE"] == [
        ("PROGRAM", "PROGRAM"), ("ID", "PRIMO"),
        ("INTEGER", "INTEGER"), ("ID", "NUM"), ("COMMA", ","), ("ID", "I"),
        ("LOGICAL", "LOGICAL"), ("ID", "ISPRIM"),
        ("PRINT", "PRINT"), ("STAR", "*"), ("COMMA", ","), ("STRING_CONST", "Introduza um numero inteiro positivo:"),
        ("READ", "READ"), ("STAR", "*"), ("COMMA", ","), ("ID", "NUM"),
        ("ID", "ISPRIM"), ("ASSIGN", "="), ("LOGICAL_CONST", True),
        ("ID", "I"), ("ASSIGN", "="), ("INTEGER_CONST", 2),
        ("LABEL", 20), ("IF", "IF"), ("LPAREN", "("), ("ID", "I"), ("LE", ".LE."),
        ("LPAREN", "("), ("ID", "NUM"), ("SLASH", "/"), ("INTEGER_CONST", 2), ("RPAREN", ")"),
        ("AND", ".AND."), ("ID", "ISPRIM"), ("RPAREN", ")"), ("THEN", "THEN"),
        ("IF", "IF"), ("LPAREN", "("), ("ID", "MOD"), ("LPAREN", "("), ("ID", "NUM"),
        ("COMMA", ","), ("ID", "I"), ("RPAREN", ")"), ("EQ", ".EQ."), ("INTEGER_CONST", 0), ("RPAREN", ")"), ("THEN", "THEN"),
        ("ID", "ISPRIM"), ("ASSIGN", "="), ("LOGICAL_CONST", False),
        ("ENDIF", "ENDIF"),
        ("ID", "I"), ("ASSIGN", "="), ("ID", "I"), ("PLUS", "+"), ("INTEGER_CONST", 1),
        ("GOTO", "GOTO"), ("INTEGER_CONST", 20),
        ("ENDIF", "ENDIF"),
        ("IF", "IF"), ("LPAREN", "("), ("ID", "ISPRIM"), ("RPAREN", ")"), ("THEN", "THEN"),
        ("PRINT", "PRINT"), ("STAR", "*"), ("COMMA", ","), ("ID", "NUM"), ("COMMA", ","), ("STRING_CONST", " e um numero primo"),
        ("ELSE", "ELSE"),
        ("PRINT", "PRINT"), ("STAR", "*"), ("COMMA", ","), ("ID", "NUM"), ("COMMA", ","), ("STRING_CONST", " nao e um numero primo"),
        ("ENDIF", "ENDIF"),
        ("END", "END"),
    ]


@pytest.mark.parametrize(
    "filename,expected_counts",
    [
        ("04_somaarr.f", {"PROGRAM": 1, "INTEGER": 2, "DO": 1, "LABEL": 1, "CONTINUE": 1, "END": 1}),
        ("05_conversor.f", {"PROGRAM": 1, "FUNCTION": 1, "DO": 1, "IF": 1, "GOTO": 1, "RETURN": 1, "END": 2}),
        ("06_ordena.f", {"PROGRAM": 1, "LOGICAL": 1, "DO": 3, "IF": 2, "LABEL": 4, "GOTO": 1, "END": 1}),
        ("07_subroutine.f", {"PROGRAM": 1, "SUBROUTINE": 1, "CALL": 1, "RETURN": 1, "END": 2}),
    ],
)
def test_remaining_examples(filename: str, expected_counts: dict[str, int]) -> None:
    """Os restantes exemplos do enunciado não geram erros e têm as contagens esperadas."""
    source = (EXAMPLES_DIR / filename).read_text(encoding="utf-8")
    toks, errors = tokenize(source)
    assert errors == []
    counts = Counter(t.type for t in toks)
    for tok_type, expected in expected_counts.items():
        assert counts[tok_type] == expected


# ======================================================================
# 6. Ficheiros .f vs .tokens em tests/lexer/
# ======================================================================

@pytest.mark.parametrize("f_path", sorted(LEXER_CASES_DIR.glob("*.f")))
def test_lexer_golden_files(f_path: Path) -> None:
    """Compara automaticamente cada .f em tests/lexer/ com o respetivo .tokens."""
    expected_path = f_path.with_suffix(".tokens")
    assert expected_path.is_file(), f"Falta ficheiro esperado: {expected_path}"

    source = f_path.read_text(encoding="utf-8")
    toks, errors = tokenize(source)
    assert errors == [], f"Erros em {f_path.name}: {errors}"

    actual_lines = [f"{t.type} {repr(t.value)}" for t in toks]
    expected_lines = [
        line.strip()
        for line in expected_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert actual_lines == expected_lines