"""Analisador léxico (lexer) para Fortran 77 em formato livre (free-form).

Baseado em ply.lex, sem pré-processador externo. Expõe `tokens`, `reserved`,
`build_lexer()`, `tokenize()`, `tokenize_with_diagnostics()` e a classe
`FortranLexer` compatível com a interface `input()`/`token()` do `ply.yacc`.
"""

import re
import ply.lex as lex
from ply.lex import LexToken

# Palavras-chave de palavra única do Fortran 77 standard.
# Nota: em Fortran 77 oficial as palavras-chave não são reservadas; nesta
# implementação assumimos que são reservadas (simplificação documentada).
reserved = {
    "PROGRAM": "PROGRAM",
    "END": "END",
    "SUBROUTINE": "SUBROUTINE",
    "FUNCTION": "FUNCTION",
    "ENTRY": "ENTRY",
    "RETURN": "RETURN",
    "STOP": "STOP",
    "PAUSE": "PAUSE",
    "CALL": "CALL",
    "INTEGER": "INTEGER",
    "REAL": "REAL",
    "COMPLEX": "COMPLEX",
    "LOGICAL": "LOGICAL",
    "CHARACTER": "CHARACTER",
    "IMPLICIT": "IMPLICIT",
    "NONE": "NONE",
    "DIMENSION": "DIMENSION",
    "PARAMETER": "PARAMETER",
    "COMMON": "COMMON",
    "DATA": "DATA",
    "EQUIVALENCE": "EQUIVALENCE",
    "EXTERNAL": "EXTERNAL",
    "INTRINSIC": "INTRINSIC",
    "SAVE": "SAVE",
    "IF": "IF",
    "THEN": "THEN",
    "ELSE": "ELSE",
    "ELSEIF": "ELSEIF",
    "ENDIF": "ENDIF",
    "DO": "DO",
    "ENDDO": "ENDDO",
    "CONTINUE": "CONTINUE",
    "GOTO": "GOTO",
    "ASSIGN": "ASSIGN_KW",
    "TO": "TO",
    "READ": "READ",
    "WRITE": "WRITE",
    "PRINT": "PRINT",
    "FORMAT": "FORMAT",
    "OPEN": "OPEN",
    "CLOSE": "CLOSE",
    "REWIND": "REWIND",
    "BACKSPACE": "BACKSPACE",
    "ENDFILE": "ENDFILE",
    "INQUIRE": "INQUIRE",
}

# Palavras-chave reconhecidas pelo lexer mas fora do âmbito das fases seguintes.
UNSUPPORTED_KEYWORDS = {
    "BLOCK_DATA",
    "ENTRY",
    "PAUSE",
    "COMPLEX",
    "DOUBLE_PRECISION",
    "IMPLICIT",
    "NONE",
    "COMMON",
    "DATA",
    "EQUIVALENCE",
    "EXTERNAL",
    "INTRINSIC",
    "SAVE",
    "ASSIGN_KW",
    "TO",
    "FORMAT",
    "OPEN",
    "CLOSE",
    "REWIND",
    "BACKSPACE",
    "ENDFILE",
    "INQUIRE",
}

# Lista oficial de tokens exportada para o ply.yacc.
tokens = (
    # Literais e identificadores
    "INTEGER_CONST",
    "REAL_CONST",
    "STRING_CONST",
    "LOGICAL_CONST",
    "ID",
    # Estrutura de instruções
    "LABEL",
    "NEWLINE",
    "FORMAT_SPEC",
    # Operadores aritméticos, concatenação e atribuição
    "PLUS",
    "MINUS",
    "STAR",
    "SLASH",
    "POWER",
    "CONCAT",
    "ASSIGN",
    # Pontuação
    "LPAREN",
    "RPAREN",
    "COMMA",
    "COLON",
    # Operadores relacionais
    "EQ",
    "NE",
    "LT",
    "LE",
    "GT",
    "GE",
    # Operadores lógicos
    "AND",
    "OR",
    "NOT",
    "EQV",
    "NEQV",
    # Palavras-chave compostas (duas palavras)
    "DOUBLE_PRECISION",
    "BLOCK_DATA",
) + tuple(reserved.values())


class LexError:
    """Erro ou aviso produzido durante a análise léxica."""

    def __init__(self, line, column, message, severity="ERROR"):
        self.line = line
        self.column = column
        self.message = message
        self.severity = severity

    def __str__(self):
        prefix = "Erro léxico" if self.severity == "ERROR" else "Aviso léxico"
        return f"{prefix} (linha {self.line}, coluna {self.column}): {self.message}"

    def __repr__(self):
        return (
            f"LexError(line={self.line}, column={self.column}, "
            f"message={self.message!r}, severity={self.severity!r})"
        )


class _PlyLexerRules:
    """Especificação das regras léxicas para o ply.lex.

    Encapsulada numa classe para evitar variáveis globais mutáveis: cada
    instância mantém as suas próprias listas de erros, avisos e estado de linha.
    """

    tokens = tokens

    # Estado exclusivo 'formatspec' usado após a palavra-chave FORMAT para
    # capturar o especificador cru sem gerar cascata de erros léxicos.
    states = (("formatspec", "exclusive"),)

    # Espaços e tabs fora de strings são ignorados (delimitadores padrão).
    t_ignore = " \t"
    t_formatspec_ignore = " \t"

    def __init__(self):
        self.errors = []
        self.warnings = []
        self._line_start = 0
        self._at_line_start = True
        self.lexer = lex.lex(
            module=self,
            reflags=re.IGNORECASE | re.MULTILINE,
        )

    def reset(self):
        """Reinicia o estado interno para analisar um novo ficheiro."""
        self.errors.clear()
        self.warnings.clear()
        self._line_start = 0
        self._at_line_start = True
        self.lexer.lineno = 1
        self.lexer.begin("INITIAL")

    def _get_col(self, lexpos):
        """Calcula a coluna (1-based) a partir da posição absoluta no texto."""
        return lexpos - self._line_start + 1

    def _emit(self, t):
        """Anota a coluna do token e marca que a linha já tem conteúdo."""
        t.col = self._get_col(t.lexpos)
        self._at_line_start = False
        return t

    def _add_error(self, lineno, lexpos, message):
        self.errors.append(
            LexError(
                line=lineno,
                column=self._get_col(lexpos),
                message=message,
                severity="ERROR",
            )
        )

    def _add_warning(self, lineno, lexpos, message):
        self.warnings.append(
            LexError(
                line=lineno,
                column=self._get_col(lexpos),
                message=message,
                severity="WARNING",
            )
        )

    # ------------------------------------------------------------------
    # Estado exclusivo: FORMAT_SPEC
    # ------------------------------------------------------------------

    def t_formatspec_FORMAT_SPEC(self, t):
        r"[^!\n]+"
        t.value = t.value.strip()
        t.lexer.begin("INITIAL")
        return self._emit(t)

    def t_formatspec_COMMENT(self, t):
        r"!.*"
        t.lexer.begin("INITIAL")

    def t_formatspec_NEWLINE(self, t):
        r"\n"
        t.lexer.begin("INITIAL")
        return self.t_NEWLINE(t)

    def t_formatspec_error(self, t):
        self._add_error(t.lineno, t.lexpos, f"carácter ilegal em FORMAT: '{t.value[0]}'")
        t.lexer.skip(1)

    # ------------------------------------------------------------------
    # Comentários e fins de linha
    # ------------------------------------------------------------------

    def t_COMMENT_COL1(self, t):
        r"^[C*].*"
        # Linha iniciada por C, c ou * na coluna 1 é comentário (regra clássica).
        pass

    def t_COMMENT_BANG(self, t):
        r"!.*"
        # Comentário até ao fim da linha ('!' dentro de string é capturado antes
        # por t_STRING_CONST quando a string começa por apóstrofo).
        pass

    def t_NEWLINE(self, t):
        r"\n"
        t.col = self._get_col(t.lexpos)
        t.lexer.lineno += 1
        self._line_start = t.lexpos + 1
        if self._at_line_start:
            # Ignorar linhas vazias ou linhas que continham apenas comentários.
            return None
        self._at_line_start = True
        return t

    # ------------------------------------------------------------------
    # Palavras-chave compostas (duas palavras)
    # Definidas ANTES de t_ID porque o PLY testa funções pela ordem de
    # definição. O \b garante que 'END' sozinho não casa com 'END IF'.
    # ------------------------------------------------------------------

    def t_GO_TO(self, t):
        r"\bGO[ \t]+TO\b"
        t.type = "GOTO"
        t.value = "GOTO"
        return self._emit(t)

    def t_END_IF(self, t):
        r"\bEND[ \t]+IF\b"
        t.type = "ENDIF"
        t.value = "ENDIF"
        return self._emit(t)

    def t_ELSE_IF(self, t):
        r"\bELSE[ \t]+IF\b"
        t.type = "ELSEIF"
        t.value = "ELSEIF"
        return self._emit(t)

    def t_END_DO(self, t):
        r"\bEND[ \t]+DO\b"
        t.type = "ENDDO"
        t.value = "ENDDO"
        return self._emit(t)

    def t_DOUBLE_PRECISION(self, t):
        r"\bDOUBLE[ \t]+PRECISION\b"
        t.type = "DOUBLE_PRECISION"
        t.value = "DOUBLE PRECISION"
        self._add_warning(
            t.lineno,
            t.lexpos,
            "palavra-chave 'DOUBLE PRECISION' reconhecida, mas não suportada nas fases seguintes.",
        )
        return self._emit(t)

    def t_BLOCK_DATA(self, t):
        r"\bBLOCK[ \t]+DATA\b"
        t.type = "BLOCK_DATA"
        t.value = "BLOCK DATA"
        self._add_warning(
            t.lineno,
            t.lexpos,
            "palavra-chave 'BLOCK DATA' reconhecida, mas não suportada nas fases seguintes.",
        )
        return self._emit(t)

    # ------------------------------------------------------------------
    # Constantes Hollerith (fora do âmbito — erro léxico explícito)
    # ------------------------------------------------------------------

    def t_HOLLERITH(self, t):
        r"\d+H"
        count = int(t.value[:-1])
        self._add_error(
            t.lineno,
            t.lexpos,
            f"constante Hollerith '{t.value}...' não é suportada neste compilador.",
        )
        remaining = len(t.lexer.lexdata) - t.lexer.lexpos
        t.lexer.skip(min(count, remaining))
        self._at_line_start = False

    # ------------------------------------------------------------------
    # Literais lógicos e operadores com ponto
    # Definidos ANTES de t_REAL_CONST para evitar conflitos com números
    # terminados em ponto (ex.: 1.EQ.2, 5.AND.X).
    # ------------------------------------------------------------------

    def t_LOGICAL_CONST(self, t):
        r"\.(?:TRUE|FALSE)\."
        t.value = t.value.upper() == ".TRUE."
        return self._emit(t)

    def t_EQ(self, t):
        r"\.EQ\."
        t.value = ".EQ."
        return self._emit(t)

    def t_NE(self, t):
        r"\.NE\."
        t.value = ".NE."
        return self._emit(t)

    def t_LT(self, t):
        r"\.LT\."
        t.value = ".LT."
        return self._emit(t)

    def t_LE(self, t):
        r"\.LE\."
        t.value = ".LE."
        return self._emit(t)

    def t_GT(self, t):
        r"\.GT\."
        t.value = ".GT."
        return self._emit(t)

    def t_GE(self, t):
        r"\.GE\."
        t.value = ".GE."
        return self._emit(t)

    def t_AND(self, t):
        r"\.AND\."
        t.value = ".AND."
        return self._emit(t)

    def t_OR(self, t):
        r"\.OR\."
        t.value = ".OR."
        return self._emit(t)

    def t_NOT(self, t):
        r"\.NOT\."
        t.value = ".NOT."
        return self._emit(t)

    def t_EQV(self, t):
        r"\.EQV\."
        t.value = ".EQV."
        return self._emit(t)

    def t_NEQV(self, t):
        r"\.NEQV\."
        t.value = ".NEQV."
        return self._emit(t)

    def t_UNKNOWN_DOT_OP(self, t):
        r"\.[A-Za-z_][A-Za-z0-9_]*\."
        self._add_error(t.lineno, t.lexpos, f"operador com ponto desconhecido '{t.value}'.")
        self._at_line_start = False

    # ------------------------------------------------------------------
    # Literais numéricos mal formados (ANTES de REAL_CONST e INTEGER_CONST)
    # ------------------------------------------------------------------

    def t_MALFORMED_NUMBER(self, t):
        r"\d+\.\d+\.[\d.]*"
        self._add_error(t.lineno, t.lexpos, f"literal numérico mal formado '{t.value}'.")
        self._at_line_start = False

    def t_MALFORMED_EXPONENT(self, t):
        r"(?:\d+\.\d*|\.\d+|\d+)[ED](?:[+-](?!\d)|(?![+-]?\d|[A-Za-z]))"
        self._add_error(t.lineno, t.lexpos, f"expoente mal formado no literal real '{t.value}'.")
        self._at_line_start = False

    # ------------------------------------------------------------------
    # Literais reais, inteiros e labels
    # `\d+\.(?![A-Za-z])` impede que `1.` seja consumido como real em `1.EQ.2`.
    # ------------------------------------------------------------------

    def t_REAL_CONST(self, t):
        r"\d+\.\d*[ED][+-]?\d+|\d+\.\d+|\.\d+(?:[ED][+-]?\d+)?|\d+\.(?![A-Za-z])|\d+[ED][+-]?\d+"
        normalized = t.value.upper().replace("D", "E")
        t.value = float(normalized)
        return self._emit(t)

    def t_INTEGER_CONST(self, t):
        r"\d+"
        if self._at_line_start:
            # No início de uma instrução, 1 a 5 dígitos formam um LABEL.
            if len(t.value) > 5:
                self._add_error(
                    t.lineno,
                    t.lexpos,
                    f"label inválido '{t.value}': um label Fortran 77 tem no máximo 5 dígitos.",
                )
                self._at_line_start = False
                return None
            t.type = "LABEL"
            t.value = int(t.value)
            return self._emit(t)

        t.value = int(t.value)
        return self._emit(t)

    # ------------------------------------------------------------------
    # Literais string (preservam maiúsculas/minúsculas; '' -> ')
    # ------------------------------------------------------------------

    def t_STRING_CONST(self, t):
        r"'(?:''|[^'\n])*'"
        t.value = t.value[1:-1].replace("''", "'")
        return self._emit(t)

    def t_UNTERMINATED_STRING(self, t):
        r"'(?:''|[^'\n])*"
        self._add_error(t.lineno, t.lexpos, "string não terminada (falta apóstrofo de fecho).")
        self._at_line_start = False

    # ------------------------------------------------------------------
    # Identificadores e palavras-chave simples
    # ------------------------------------------------------------------

    def t_ID(self, t):
        r"[A-Za-z][A-Za-z0-9_]*"
        upper_val = t.value.upper()
        t.type = reserved.get(upper_val, "ID")
        t.value = upper_val

        if t.type == "FORMAT":
            self._add_warning(
                t.lineno,
                t.lexpos,
                "palavra-chave 'FORMAT' reconhecida, mas não suportada nas fases seguintes.",
            )
            t.lexer.begin("formatspec")
        elif t.type in UNSUPPORTED_KEYWORDS:
            self._add_warning(
                t.lineno,
                t.lexpos,
                f"palavra-chave '{t.value}' reconhecida, mas não suportada nas fases seguintes.",
            )

        return self._emit(t)

    # ------------------------------------------------------------------
    # Operadores de 2 caracteres (ANTES dos de 1 carácter) e pontuação
    # ------------------------------------------------------------------

    def t_POWER(self, t):
        r"\*\*"
        return self._emit(t)

    def t_CONCAT(self, t):
        r"//"
        return self._emit(t)

    def t_PLUS(self, t):
        r"\+"
        return self._emit(t)

    def t_MINUS(self, t):
        r"-"
        return self._emit(t)

    def t_STAR(self, t):
        r"\*"
        return self._emit(t)

    def t_SLASH(self, t):
        r"/"
        return self._emit(t)

    def t_ASSIGN(self, t):
        r"="
        return self._emit(t)

    def t_LPAREN(self, t):
        r"\("
        return self._emit(t)

    def t_RPAREN(self, t):
        r"\)"
        return self._emit(t)

    def t_COMMA(self, t):
        r","
        return self._emit(t)

    def t_COLON(self, t):
        r":"
        return self._emit(t)

    def t_error(self, t):
        self._add_error(t.lineno, t.lexpos, f"carácter ilegal '{t.value[0]}'")
        t.lexer.skip(1)
        self._at_line_start = False


class FortranLexer:
    """Wrapper de alto nível compatível com a interface do ply.yacc.

    Normaliza fins de linha, recolhe os tokens (garantindo `NEWLINE` no fim da
    última instrução) e expõe `input(source)` e `token()` para o parser.
    """

    def __init__(self):
        self._rules = _PlyLexerRules()
        self._tokens = []
        self._index = 0
        self.errors = []
        self.warnings = []

    def input(self, source):
        """Tokeniza o código-fonte completo."""
        normalized = source.replace("\r\n", "\n").replace("\r", "\n")
        self._rules.reset()
        self._rules.lexer.input(normalized)

        self._tokens = []
        self._index = 0

        while True:
            tok = self._rules.lexer.token()
            if tok is None:
                break
            self._tokens.append(tok)

        # Garantir NEWLINE no fim da última instrução mesmo sem '\n' final.
        if not self._rules._at_line_start:
            nl_tok = LexToken()
            nl_tok.type = "NEWLINE"
            nl_tok.value = "\n"
            nl_tok.lineno = self._rules.lexer.lineno
            nl_tok.lexpos = len(normalized)
            nl_tok.col = self._rules._get_col(len(normalized))
            self._tokens.append(nl_tok)

        self.errors = list(self._rules.errors)
        self.warnings = list(self._rules.warnings)

    def token(self):
        """Devolve o próximo token do fluxo (interface exigida pelo ply.yacc)."""
        if self._index < len(self._tokens):
            tok = self._tokens[self._index]
            self._index += 1
            return tok
        return None

    def get_all_tokens(self):
        """Devolve uma cópia da lista completa de tokens produzidos."""
        return list(self._tokens)


def build_lexer():
    """Constrói e devolve uma nova instância isolada de `FortranLexer`."""
    return FortranLexer()


def tokenize_with_diagnostics(source):
    """Executa a análise léxica devolvendo `(tokens, errors, warnings)`."""
    lexer = build_lexer()
    lexer.input(source)
    return lexer.get_all_tokens(), lexer.errors, lexer.warnings


def tokenize(source):
    """Executa a análise léxica devolvendo `(tokens, errors)`."""
    tokens_list, errors, _warnings = tokenize_with_diagnostics(source)
    return tokens_list, errors