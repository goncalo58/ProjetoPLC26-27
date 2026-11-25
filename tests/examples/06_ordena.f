PROGRAM ORDENA
        INTEGER NUMS(5)
        INTEGER I, N, TEMP
        LOGICAL TROCOU
C       Leitura dos dados
        PRINT *, 'Introduza 5 numeros inteiros para ordenar:'
        DO 10 I = 1, 5
          READ *, NUMS(I)
   10   CONTINUE
        N = 5
C       Algoritmo Bubble Sort Otimizado (com paragem antecipada)
   20   TROCOU = .FALSE.
        DO 30 I = 1, N - 1
          IF (NUMS(I) .GT. NUMS(I+1)) THEN
            TEMP = NUMS(I)
            NUMS(I) = NUMS(I+1)
            NUMS(I+1) = TEMP
            TROCOU = .TRUE.
          ENDIF
   30   CONTINUE
C       Apos cada passagem, o maior elemento vai para o fim
        N = N - 1
C       Se houve trocas e ainda ha elementos para ordenar, repete
        IF (TROCOU .AND. N .GT. 1) GOTO 20
C       Impressao dos dados ordenados
        PRINT *, 'Array ordenado:'
        DO 40 I = 1, 5
          PRINT *, NUMS(I)
   40   CONTINUE
      END