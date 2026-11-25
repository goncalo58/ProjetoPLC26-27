PROGRAM TESTSUB
        INTEGER A, B
        A = 10
        B = 25
        PRINT *, 'Antes da troca: A = ', A, ' B = ', B
        CALL TROCA(A, B)
        PRINT *, 'Depois da troca: A = ', A, ' B = ', B
      END

      SUBROUTINE TROCA(X, Y)
        INTEGER X, Y, AUX
        AUX = X
        X = Y
        Y = AUX
        RETURN
      END