PROGRAM AMB
        INTEGER A, B
        LOGICAL F
        F = 1.EQ.2
        F = 5.AND.F
        F = A.LT.5.
        A = 2**3*4
        IF (F) THEN
          A = 1
        ELSE IF (A .EQ. 1) THEN
          A = 2
        END IF
        GO TO 10
   10   END