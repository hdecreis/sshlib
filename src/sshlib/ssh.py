import os
import sys
import socket
import select
import paramiko

__all__ = ["Ssh"]

# Tunable parameters
DEBUGLEVEL = 0

# Telnet protocol defaults
SSH_PORT = 22

class Ssh:

    """SSH interface class. bare copy/paste of telnetlib with
	raw sockets replaced with paramiko transport and interactive channel,
	and telnet options / special chars just removed.

    An instance of this class represents a connection to a telnet
    server.  The instance is initially not connected; the open()
    method must be used to establish a connection.  Alternatively, the
    host name and optional port number can be passed to the
    constructor, too.

    Don't try to reopen an already connected instance.

    This class has many read_*() methods.  Note that some of them
    raise EOFError when the end of the connection is read, because
    they can return an empty string for other reasons.  See the
    individual doc strings.

    read_until(expected, [timeout])
        Read until the expected string has been seen, or a timeout is
        hit (default is no timeout); may block.

    read_all()
        Read all data until EOF; may block.

    read_some()
        Read at least one byte or EOF; may block.

    read_very_eager()
        Read all data available already queued or on the socket,
        without blocking.

    read_eager()
        Read either data already queued or some data available on the
        socket, without blocking.

    read_lazy()
        Read all data in the raw queue (processing it first), without
        doing any socket I/O.

    read_very_lazy()
        Reads all data in the cooked queue, without doing any socket
        I/O.

    read_sb_data()
        Reads available data between SB ... SE sequence. Don't block.

    set_option_negotiation_callback(callback)
        Each time a telnet option is read on the input flow, this callback
        (if set) is called with the following parameters :
        callback(telnet socket, command, option)
            option will be chr(0) when there is no option.
        No other action is done afterwards by telnetlib.

    """

    def __init__(self, host=None, port=0,
                 timeout=socket.getdefaulttimeout()):
        """Constructor.

        When called without arguments, create an unconnected instance.
        With a hostname argument, it connects the instance; port number
        and timeout are optional.
        """
        self.debuglevel = DEBUGLEVEL
        self.host = host
        self.port = port
        self.timeout = timeout

        # ssh specific (paramiko)
        self.transport = None
        self.chan = None
        self.hostkeytype = None
        self.hostkey = None
        self.hosttype = None

        try:
            import termios
            import tty
            self.posix = True
        except ImportError:
            self.posix = False

        self.sb = 0
        self.eof = 0
        self.irawq = 0
        self.rawq = ''
        self.cookedq = ''
        self.option_callback = None
        if host is not None:
            self.open(host, port, timeout)

    def open(self, host, port=0, timeout=socket.getdefaulttimeout()):
        """Connect to a host.

        The optional second argument is the port number, which
        defaults to the standard telnet port (23).

        Don't try to reopen an already connected instance.
        """
        self.eof = 0
        if not port:
            port = SSH_PORT
        self.host = host
        self.port = port
        self.timeout = timeout
        ###TELNET### self.sock = socket.create_connection((host, port), timeout)
        self.transport = paramiko.Transport((host,port))

    def get_host_key(self):
        try:
            host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        except IOError:
            try:
                # try ~/ssh/ too, because windows can't have a folder named ~/.ssh/
                host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
            except IOError:
                print '*** Unable to open host keys file'
                host_keys = {}

        if host_keys.has_key(self.host):
            self.hostkeytype = host_keys[self.host].keys()[0]
            self.hostkey = host_keys[self.host][self.hostkeytype]
            print 'Using host key of type %s' % self.hostkeytype
        

    def login(self, inUser=None, inPassword=None):
        if(self.hostkey == None):
            self.get_host_key()
        self.transport.connect(username=inUser, password=inPassword, hostkey=self.hostkey)
        self.chan = self.transport.open_session()
        self.chan.get_pty()
        self.chan.invoke_shell()
        self.chan.settimeout(self.timeout)
        ### now self.chan can be used by interactive.

    def interactive_shell(self,chan):
        if self.posix:
            posix_shell(chan)
        else:
            windows_shell(chan)

    def close(self):
        self.chan.close()
        self.transport.close()













    def __del__(self):
        """Destructor -- close the connection."""
        self.close()

    def msg(self, msg, *args):
        """Print a debug message, when the debug level is > 0.

        If extra arguments are present, they are substituted in the
        message using the standard string formatting operator.

        """
        if self.debuglevel > 0:
            print 'SSH(%s,%d):' % (self.host, self.port),
            if args:
                print msg % args
            else:
                print msg

    def set_debuglevel(self, debuglevel):
        """Set the debug level.

        The higher it is, the more debug output you get (on sys.stdout).

        """
        self.debuglevel = debuglevel

    def get_socket(self):
        """Return the socket object used internally."""
        return self.chan

    def fileno(self):
        """Return the fileno() of the socket object used internally."""
        return self.chan.fileno()

    def write(self, buffer):
        """Write a string to the socket

        Can block if the connection is blocked.  May raise
        socket.error if the connection is closed.

        """
        self.msg("send %r", buffer)
        self.chan.send(buffer)


    ################ NOW REAL JOB: REPLACE ALL THIS WITH READING THE CHAN








    def read_until(self, match, timeout=None):
        """Read until a given string is encountered or until timeout.

        When no match is found, return whatever is available instead,
        possibly the empty string.  Raise EOFError if the connection
        is closed and no cooked data is available.

        """
        n = len(match)
        self.process_rawq()
        i = self.cookedq.find(match)
        if i >= 0:
            i = i+n
            buf = self.cookedq[:i]
            self.cookedq = self.cookedq[i:]
            return buf
        s_reply = ([self], [], [])
        s_args = s_reply
        if timeout is not None:
            s_args = s_args + (timeout,)
            from time import time
            time_start = time()
        while not self.eof and select.select(*s_args) == s_reply:
            i = max(0, len(self.cookedq)-n)
            self.fill_rawq()
            self.process_rawq()
            i = self.cookedq.find(match, i)
            if i >= 0:
                i = i+n
                buf = self.cookedq[:i]
                self.cookedq = self.cookedq[i:]
                return buf
            if timeout is not None:
                elapsed = time() - time_start
                if elapsed >= timeout:
                    break
                s_args = s_reply + (timeout-elapsed,)
        return self.read_very_lazy()

    def read_all(self):
        """Read all data until EOF; block until connection closed."""
        self.process_rawq()
        while not self.eof:
            self.fill_rawq()
            self.process_rawq()
        buf = self.cookedq
        self.cookedq = ''
        return buf

    def read_some(self):
        """Read at least one byte of cooked data unless EOF is hit.

        Return '' if EOF is hit.  Block if no data is immediately
        available.

        """
        self.process_rawq()
        while not self.cookedq and not self.eof:
            self.fill_rawq()
            self.process_rawq()
        buf = self.cookedq
        self.cookedq = ''
        return buf

    def read_very_eager(self):
        """Read everything that's possible without blocking in I/O (eager).

        Raise EOFError if connection closed and no cooked data
        available.  Return '' if no cooked data available otherwise.
        Don't block unless in the midst of an IAC sequence.

        """
        self.process_rawq()
        while not self.eof and self.sock_avail():
            self.fill_rawq()
            self.process_rawq()
        return self.read_very_lazy()

    def read_eager(self):
        """Read readily available data.

        Raise EOFError if connection closed and no cooked data
        available.  Return '' if no cooked data available otherwise.
        Don't block unless in the midst of an IAC sequence.

        """
        self.process_rawq()
        while not self.cookedq and not self.eof and self.sock_avail():
            self.fill_rawq()
            self.process_rawq()
        return self.read_very_lazy()

    def read_lazy(self):
        """Process and return data that's already in the queues (lazy).

        Raise EOFError if connection closed and no data available.
        Return '' if no cooked data available otherwise.  Don't block
        unless in the midst of an IAC sequence.

        """
        self.process_rawq()
        return self.read_very_lazy()

    def read_very_lazy(self):
        """Return any data available in the cooked queue (very lazy).

        Raise EOFError if connection closed and no data available.
        Return '' if no cooked data available otherwise.  Don't block.

        """
        buf = self.cookedq
        self.cookedq = ''
        if not buf and self.eof and not self.rawq:
            raise EOFError, 'telnet connection closed'
        return buf

    def process_rawq(self):
        """Transfer from raw queue to cooked queue.

        Set self.eof when connection is closed.

        """
        buf = ['', '']
        try:
            while self.rawq:
                c = self.rawq_getchar()
                if c == '\0':
                    continue
                if c == '\021':
                    continue
                else:
                    buf[self.sb] = buf[self.sb] + c
                    continue
        except EOFError: # raised by self.rawq_getchar()
            self.sb = 0
            pass
        self.cookedq = self.cookedq + buf[0]

    def rawq_getchar(self):
        """Get next char from raw queue.

        Block if no data is immediately available.  Raise EOFError
        when connection is closed.

        """
        if not self.rawq:
            self.fill_rawq()
            if self.eof:
                raise EOFError
        c = self.rawq[self.irawq]
        self.irawq = self.irawq + 1
        if self.irawq >= len(self.rawq):
            self.rawq = ''
            self.irawq = 0
        return c

    def fill_rawq(self):
        """Fill raw queue from exactly one recv() system call.

        Block if no data is immediately available.  Set self.eof when
        connection is closed.

        """
        if self.irawq >= len(self.rawq):
            self.rawq = ''
            self.irawq = 0
        # The buffer size should be fairly small so as to avoid quadratic
        # behavior in process_rawq() above
        buf = self.chan.recv(50)
        self.msg("recv %r", buf)
        self.eof = (not buf)
        self.rawq = self.rawq + buf

    def sock_avail(self):
        """Test whether data is available on the socket."""
        return select.select([self], [], [], 0) == ([self], [], [])

    def interact(self):
        """Interaction function, emulates a very dumb telnet client."""
        if sys.platform == "win32":
            self.mt_interact()
            return
        while 1:
            rfd, wfd, xfd = select.select([self, sys.stdin], [], [])
            if self in rfd:
                try:
                    text = self.read_eager()
                except EOFError:
                    print '*** Connection closed by remote host ***'
                    break
                if text:
                    sys.stdout.write(text)
                    sys.stdout.flush()
            if sys.stdin in rfd:
                line = sys.stdin.readline()
                if not line:
                    break
                self.write(line)

    def mt_interact(self):
        """Multithreaded version of interact()."""
        import thread
        thread.start_new_thread(self.listener, ())
        while 1:
            line = sys.stdin.readline()
            if not line:
                break
            self.write(line)

    def listener(self):
        """Helper for mt_interact() -- this executes in the other thread."""
        while 1:
            try:
                data = self.read_eager()
            except EOFError:
                print '*** Connection closed by remote host ***'
                return
            if data:
                sys.stdout.write(data)
            else:
                sys.stdout.flush()

    def expect(self, list, timeout=None):
        """Read until one from a list of a regular expressions matches.

        The first argument is a list of regular expressions, either
        compiled (re.RegexObject instances) or uncompiled (strings).
        The optional second argument is a timeout, in seconds; default
        is no timeout.

        Return a tuple of three items: the index in the list of the
        first regular expression that matches; the match object
        returned; and the text read up till and including the match.

        If EOF is read and no text was read, raise EOFError.
        Otherwise, when nothing matches, return (-1, None, text) where
        text is the text received so far (may be the empty string if a
        timeout happened).

        If a regular expression ends with a greedy match (e.g. '.*')
        or if more than one expression can match the same input, the
        results are undeterministic, and may depend on the I/O timing.

        """
        re = None
        list = list[:]
        indices = range(len(list))
        for i in indices:
            if not hasattr(list[i], "search"):
                if not re: import re
                list[i] = re.compile(list[i])
        if timeout is not None:
            from time import time
            time_start = time()
        while 1:
            self.process_rawq()
            for i in indices:
                m = list[i].search(self.cookedq)
                if m:
                    e = m.end()
                    text = self.cookedq[:e]
                    self.cookedq = self.cookedq[e:]
                    return (i, m, text)
            if self.eof:
                break
            if timeout is not None:
                elapsed = time() - time_start
                if elapsed >= timeout:
                    break
                s_args = ([self.fileno()], [], [], timeout-elapsed)
                r, w, x = select.select(*s_args)
                if not r:
                    break
            self.fill_rawq()
        text = self.read_very_lazy()
        if not text and self.eof:
            raise EOFError
        return (-1, None, text)

