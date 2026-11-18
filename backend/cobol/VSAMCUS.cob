       IDENTIFICATION DIVISION.
       PROGRAM-ID. VSAMCUS.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUSTOMER-FILE ASSIGN TO "CUSTOMER.KSDS"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS CUSTOMER-ID
               FILE STATUS IS WS-FILE-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD CUSTOMER-FILE.
       01 CUSTOMER-RECORD.
           05 CUSTOMER-ID PIC X(8).
           05 CUSTOMER-NAME PIC X(40).
       WORKING-STORAGE SECTION.
       01 WS-FILE-STATUS PIC XX.
       01 WS-INPUT PIC X(120).
       01 WS-ACTION PIC X(8).
       01 WS-ID PIC X(8).
       01 WS-NAME PIC X(40).
       PROCEDURE DIVISION.
           ACCEPT WS-INPUT.
           UNSTRING WS-INPUT DELIMITED BY "|"
               INTO WS-ACTION WS-ID WS-NAME.
           OPEN INPUT CUSTOMER-FILE.
           IF WS-FILE-STATUS = "35"
               OPEN OUTPUT CUSTOMER-FILE
               IF WS-FILE-STATUS = "00"
                   CLOSE CUSTOMER-FILE
               ELSE
                   DISPLAY "ERROR|OPEN"
                   STOP RUN RETURNING 1
               END-IF
           ELSE
               CLOSE CUSTOMER-FILE
           END-IF.
           OPEN I-O CUSTOMER-FILE.
           IF WS-FILE-STATUS NOT = "00"
               DISPLAY "ERROR|OPEN"
               STOP RUN RETURNING 1
           END-IF.
           MOVE WS-ID TO CUSTOMER-ID.
           EVALUATE WS-ACTION
               WHEN "ADD"
                   MOVE WS-NAME TO CUSTOMER-NAME
                   WRITE CUSTOMER-RECORD
                       INVALID KEY DISPLAY "ERROR|DUPLICATE"
                       NOT INVALID KEY
                           DISPLAY "OK|" CUSTOMER-ID "|"
                               CUSTOMER-NAME
                   END-WRITE
               WHEN "GET"
                   READ CUSTOMER-FILE KEY IS CUSTOMER-ID
                       INVALID KEY DISPLAY "ERROR|NOTFOUND"
                       NOT INVALID KEY
                           DISPLAY "OK|" CUSTOMER-ID "|"
                               CUSTOMER-NAME
                   END-READ
               WHEN "UPDATE"
                   READ CUSTOMER-FILE KEY IS CUSTOMER-ID
                       INVALID KEY DISPLAY "ERROR|NOTFOUND"
                       NOT INVALID KEY
                           MOVE WS-NAME TO CUSTOMER-NAME
                           REWRITE CUSTOMER-RECORD
                               INVALID KEY DISPLAY "ERROR|UPDATE"
                               NOT INVALID KEY
                                   DISPLAY "OK|" CUSTOMER-ID "|"
                                       CUSTOMER-NAME
                           END-REWRITE
                   END-READ
               WHEN "DELETE"
                   READ CUSTOMER-FILE KEY IS CUSTOMER-ID
                       INVALID KEY DISPLAY "ERROR|NOTFOUND"
                       NOT INVALID KEY
                           DELETE CUSTOMER-FILE RECORD
                               INVALID KEY DISPLAY "ERROR|DELETE"
                               NOT INVALID KEY
                                   DISPLAY "OK|" CUSTOMER-ID "|"
                                       CUSTOMER-NAME
                           END-DELETE
                   END-READ
               WHEN "LIST"
                   MOVE SPACES TO CUSTOMER-ID
                   START CUSTOMER-FILE KEY IS NOT LESS THAN CUSTOMER-ID
                       INVALID KEY DISPLAY "EMPTY"
                       NOT INVALID KEY
                           PERFORM UNTIL WS-FILE-STATUS = "10"
                               READ CUSTOMER-FILE NEXT RECORD
                                   AT END MOVE "10" TO WS-FILE-STATUS
                                   NOT AT END
                                       DISPLAY "OK|" CUSTOMER-ID "|"
                                           CUSTOMER-NAME
                               END-READ
                           END-PERFORM
                   END-START
               WHEN OTHER
                   DISPLAY "ERROR|ACTION"
           END-EVALUATE.
           CLOSE CUSTOMER-FILE.
           STOP RUN.
