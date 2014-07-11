#!/usr/bin/env python

import string, sys
from distutils.core import setup

myVersion = "$Revision: 0.1 $";

# We requre Python 2.0
pyversion = string.split( string.split( sys.version )[0], "." )

if map( int, pyversion ) < [2, 0, 0]:
    sys.stderr.write( "Sorry, this library requires at least Python 2.0\n" )
    sys.exit(1);

# Call the distutils setup function to install ourselves
setup ( name         = "sshlib",
        version      = myVersion.split()[-2],
        description  = "Python Shameless copy of telnetlib to Paramiko's SSH library",
        author       = "Copyist: Helios de Creisquer",
        author_email = "creis@balios.net",
        url          = "http://sshlib.sourceforge.net",

        package_dir  = { '': 'src' },
        packages     = [ 'sshlib' ]
      )
