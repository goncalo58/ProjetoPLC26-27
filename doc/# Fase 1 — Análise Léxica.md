# Fase 1 — Análise Léxica

## 1. Decisões de Arquitetura

O analisador léxico foi implementado em Python com `ply.lex` num único módulo (`src/lexer.py`), adotando **formato livre (*free-form*)**, opção explicitamente prevista no enunciado. Esta escolha elimina a necessidade de um pré-processador separado, reduzindo a complexidade do código sem comprometer a correção sobre os programas Fortran 77 alvo.

Principais decisões:
- **Encapsulamento sem estado global**: as regras léxicas estão encapsuladas em `_PlyLexerRules` e expostas através do wrapper `FortranLexer`. A função `build_lexer()` devolve sempre uma instância isolada, evitando contaminação de erros ou estado entre análises.
- **Compatibilidade com `ply.yacc` (Fase 2)**: `FortranLexer` implementa `input(source)` e `token()`, garantindo um token `NEWLINE` no fim de cada instrução não vazia (incluindo a última linha do ficheiro).
- **Distinção entre `LABEL` e `INTEGER_CONST`**: uma flag booleana `_at_line_start` indica se ainda não foi emitido nenhum token na linha atual. Se aparecer um inteiro (1 a 5 dígitos) nessa posição, é emitido como `LABEL`; todos os restantes inteiros (`DO 10 I = 1, N`, `GOTO 20`) são `INTEGER_CONST`.
- **Insensibilidade a maiúsculas/minúsculas**: ativada via `re.IGNORECASE`, normalizando palavras-chave e identificadores para maiúsculas. Os literais `STRING_CONST` preservam o texto original.
- **Identificadores**: aceitam o carácter `_` após a primeira letra (`[A-Za-z][A-Za-z0-9_]*`), mantendo compatibilidade com ANSI X3.9-1978 e com extensões comuns de Fortran 77.
- **Token `*` único (`STAR`)**: usado em multiplicação, `PRINT *,`, `READ(*,*)` e `CHARACTER*10`; a distinção é sintática (Fase 2).
- **Funções intrínsecas**: `MOD`, `ABS`, `SQRT`, `MAX`, `MIN`, etc. saem como `ID` e são resolvidas na análise semântica. `REAL` e `INTEGER` existem como palavras-chave de tipo; a ambiguidade com funções de conversão será tratada no parser.

## 2. Tabela Completa de Tokens

| Token | Expressão Regular / Origem | Exemplo |
| --- | --- | --- |
| `INTEGER_CONST` | `\d+` (fora do início da linha) | `42` |
| `LABEL` | `\d{1,5}` (no início da linha) | `10` |
| `REAL_CONST` | `\d+\.\d*[ED][+-]?\d+\|\d+\.\d+\|\.\d+(?:[ED][+-]?\d+)?\|\d+\.(?![A-Za-z])\|\d+[ED][+-]?\d+` | `3.14`, `.5`, `2.`, `1.0D-3`, `1E3` |
| `LOGICAL_CONST` | `\.(?:TRUE\|FALSE)\.` | `.TRUE.`, `.FALSE.` |
| `STRING_CONST` | `'(?:''\|[^'\n])*'` | `'Ola, Mundo!'` |
| `ID` | `[A-Za-z][A-Za-z0-9_]*` (não reservado) | `FATORIAL`, `NUMS` |
| `NEWLINE` | `\n` (em linhas não vazias) | `\n` |
| `FORMAT_SPEC` | `[^!\n]+` (estado exclusivo `formatspec`) | `(I5, 2X)` |
| `PLUS` / `MINUS` | `\+` / `-` | `+`, `-` |
| `STAR` / `SLASH` | `\*` / `/` | `*`, `/` |
| `POWER` / `CONCAT` | `\*\*` / `//` | `**`, `//` |
| `ASSIGN` | `=` | `=` |
| `LPAREN` / `RPAREN` | `\(` / `\)` | `(`, `)` |
| `COMMA` / `COLON` | `,` / `:` | `,`, `:` |
| `EQ`, `NE`, `LT`, `LE`, `GT`, `GE` | `\.EQ\.`, `\.NE\.`, `\.LT\.`, `\.LE\.`, `\.GT\.`, `\.GE\.` | `.EQ.`, `.LE.` |
| `AND`, `OR`, `NOT`, `EQV`, `NEQV` | `\.AND\.`, `\.OR\.`, `\.NOT\.`, `\.EQV\.`, `\.NEQV\.` | `.AND.`, `.NOT.` |
| `GOTO` | `\bGO[ \t]+TO\b` ou `reserved["GOTO"]` | `GOTO`, `GO TO` |
| `ENDIF` | `\bEND[ \t]+IF\b` ou `reserved["ENDIF"]` | `ENDIF`, `END IF` |
| `ELSEIF` | `\bELSE[ \t]+IF\b` ou `reserved["ELSEIF"]` | `ELSEIF`, `ELSE IF` |
| `ENDDO` | `\bEND[ \t]+DO\b` ou `reserved["ENDDO"]` | `ENDDO`, `END DO` |
| `DOUBLE_PRECISION` | `\bDOUBLE[ \t]+PRECISION\b` | `DOUBLE PRECISION` |
| `BLOCK_DATA` | `\bBLOCK[ \t]+DATA\b` | `BLOCK DATA` |
| Palavras-chave simples | Dicionário `reserved` em `t_ID`: `PROGRAM`, `END`, `SUBROUTINE`, `FUNCTION`, `ENTRY`, `RETURN`, `STOP`, `PAUSE`, `CALL`, `INTEGER`, `REAL`, `COMPLEX`, `LOGICAL`, `CHARACTER`, `IMPLICIT`, `NONE`, `DIMENSION`, `PARAMETER`, `COMMON`, `DATA`, `EQUIVALENCE`, `EXTERNAL`, `INTRINSIC`, `SAVE`, `IF`, `THEN`, `ELSE`, `ELSEIF`, `ENDIF`, `DO`, `ENDDO`, `CONTINUE`, `GOTO`, `ASSIGN_KW` (`ASSIGN`), `TO`, `READ`, `WRITE`, `PRINT`, `FORMAT`, `OPEN`, `CLOSE`, `REWIND`, `BACKSPACE`, `ENDFILE`, `INQUIRE` | `PROGRAM`, `INTEGER`, `CONTINUE` |

## 3. Ambiguidades Clássicas e Resolução

1. **`1.EQ.2` e `5.AND.X`**: a alternativa `\d+\.(?![A-Za-z])` em `t_REAL_CONST` usa *lookahead* negativo para impedir que `1.` seja consumido como real quando o ponto pertence a um operador com ponto. Além disso, os operadores com ponto são definidos antes de `t_REAL_CONST`.
2. **`**` vs `*` e `//` vs `/`**: como o PLY testa funções pela ordem de definição, `t_POWER` e `t_CONCAT` precedem `t_STAR` e `t_SLASH`.
3. **`END` vs `END IF` / `END DO` (e `GO TO` / `ELSE IF`)**: as regras de duas palavras usam `\b...\b` e são definidas antes de `t_ID`, garantindo que `END` isolado nunca é confundido com `END IF` nem `END IFX` com `ENDIF`.
4. **Comentário `!` dentro de strings**: `t_STRING_CONST` consome a string inteira quando o lexer encontra `'`, pelo que `!` dentro de aspas não ativa `t_COMMENT_BANG`.
5. **`FORMAT (I5, 2X)`**: ao reconhecer `FORMAT`, o lexer entra no estado exclusivo `formatspec`, captura o resto da linha como `FORMAT_SPEC` e emite um aviso, evitando cascatas de erros léxicos.

## 4. Tratamento e Recuperação de Erros

Todos os erros léxicos são acumulados na lista `lexer.errors` (sem abortar a análise) com linha e coluna originais (`lexpos - _line_start + 1`):
- **Caracteres ilegais** (`@`, `#`, `$`, `?`, ...): reportados em `t_error` com `skip(1)`.
- **Strings não terminadas**: capturadas por `t_UNTERMINATED_STRING`.
- **Literais numéricos mal formados**: `1.2.3` (`t_MALFORMED_NUMBER`) e expoentes sem dígitos como `1E+` (`t_MALFORMED_EXPONENT`).
- **Operadores com ponto desconhecidos**: `.FOO.` (`t_UNKNOWN_DOT_OP`).
- **Labels inválidos**: números com mais de 5 dígitos no início da linha.
- **Constantes Hollerith** (`5HOLA`): detetadas explicitamente em `t_HOLLERITH` como erro léxico.

## 5. Limitações e Simplificações Assumidas

- **Palavras-chave reservadas**: não é permitido usar palavras-chave (`TO`, `NONE`, `DATA`, etc.) como nomes de variáveis.
- **Espaços como delimitadores**: não são suportadas formas sem espaços como `DO10I=1,5` (simplificação permitida pelo enunciado).
- **Comentários na coluna 1**: linhas que comecem na coluna 1 por `C`, `c` ou `*` são sempre tratadas como comentário; instruções como `CALL X` devem estar indentadas.
- **Formato livre**: não são suportadas linhas de continuação na coluna 6 nem truncagem na coluna 72.
- **Fora do âmbito**: constantes Hollerith, `IF` aritmético, `GOTO` computado e palavras-chave avançadas (`FORMAT`, `COMPLEX`, `DOUBLE PRECISION`, `COMMON`, `DATA`, `EQUIVALENCE`, `OPEN`, `CLOSE`, etc.), que são reconhecidas com aviso mas não suportadas nas fases seguintes.

## 6. Instalação, Execução e Testes

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install ply pytest

# Executar análise léxica sobre um ficheiro
python src/fortran_compiler.py --tokens tests/examples/02_fatorial.f

# Correr a suite de testes
pytest -v