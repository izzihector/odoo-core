# -*- coding: utf-8 -*-

import ftplib
import socket
import ssl


PathFile = ''
ftplib.FTP_PORT = 992
_SSLSocket = ssl.SSLSocket


class ChariotsFTP(ftplib.FTP_TLS):

    def __init__(self,
                 host='',
                 user='',
                 passwd='',
                 acct='',
                 keyfile=None,
                 certfile=None,
                 timeout=60):


        ftplib.FTP_TLS.__init__(self,
                                host=host,
                                user=user,
                                passwd=passwd,
                                acct=acct,
                                keyfile=keyfile,
                                certfile=certfile,
                                timeout=timeout)    

    def storbinary(self, cmd, fp, blocksize=8192, callback=None, rest=None):
        """Store a file in binary mode.  A new port is created for you.

        Args:
          cmd: A STOR command.
          fp: A file-like object with a read(num_bytes) method.
          blocksize: The maximum data size to read from fp and send over
                     the connection at once.  [default: 8192]
          callback: An optional single parameter callable that is called on
                    each block of data after it is sent.  [default: None]
          rest: Passed to transfercmd().  [default: None]

        Returns:
          The response code.
        """
        self.voidcmd('TYPE I')
        conn = self.transfercmd(cmd, rest)
        try:
            while 1:
                buf = fp.read(blocksize)
                if not buf:
                    break
                conn.sendall(buf)
                if callback:
                    callback(buf)
            if isinstance(conn, ssl.SSLSocket):
                pass
        #         conn.unwrap()
        finally:
            conn.close()
        return self.voidresp()

    def connect(self, host='', port=0, timeout=-999):
        """Connect to host.  Arguments are:
            - host: hostname to connect to (string, default previous host)
            - port: port to connect to (integer, default previous port)
        """
        if host != '':
            self.host = host
        if port > 0:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        try:
            self.sock = socket.create_connection((self.host, self.port), self.timeout)
            self.af = self.sock.family
            # add this line!!!
            self.sock = ssl.wrap_socket(
                self.sock,
                self.keyfile,
                self.certfile,
                # cert_reqs=ssl.CERT_NONE,
                # ssl_version=ssl.PROTOCOL_TLSv1_2,
                # certfile="ssl/win2012r2.crt", keyfile="ssl/win2012r2.key",
                ssl_version=ssl.PROTOCOL_TLSv1
            )  # this is the fix
            # add end
            self.file = self.sock.makefile('r')
            self.welcome = self.getresp()
        except Exception as e:
            print(e)
        return self.welcome
