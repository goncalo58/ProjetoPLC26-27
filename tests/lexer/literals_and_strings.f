C Comentario na coluna 1
* Outro comentario
      PROGRAM LITS
        REAL R1, R2, R3, R4
        CHARACTER*10 NOME ! comentario inline
        R1 = .5
        R2 = 2.
        R3 = 1.0D-3
        R4 = 1E3
        NOME = 'd''agua ! nao e comentario'
        PRINT *, NOME // '!'
      END